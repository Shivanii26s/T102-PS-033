
from datetime import date, datetime

from src.models.entities import StockLot, Movement


class InventoryService:
    """Inventory ledger keyed by (bin_id, sku_id, lot_no)."""

    PICKABLE_STATUSES = {"AVAILABLE", "SLOW"}

    def __init__(self, warehouse=None, sku_master=None):
        self.warehouse = warehouse
        self.sku_master = sku_master or {}
        self.stock: dict[tuple, StockLot] = {}
        self.movements: list[Movement] = []
        self.frozen_bins: set[str] = set()

    @staticmethod
    def _key(bin_id, sku_id, lot_no):
        return bin_id, sku_id, lot_no

    def _check_not_frozen(self, bin_id, operation):
        if bin_id in self.frozen_bins:
            raise ValueError(
                f"Bin {bin_id} is frozen; cannot perform {operation}"
            )

    def _validate_location(self, bin_id, sku_id, qty, status="AVAILABLE"):
        if qty <= 0:
            raise ValueError("Quantity must be positive")

        if self.warehouse:
            bin_obj = self.warehouse.get_bin(bin_id)
            sku = self.sku_master.get(sku_id)

            if sku and bin_obj.temp_class != sku["temp_class"]:
                raise ValueError(
                    f"Temperature mismatch: SKU {sku_id} cannot be stored in {bin_id}"
                )

            if bin_obj.bin_type == "QUARANTINE" and status != "QUARANTINE":
                raise ValueError(
                    "Only quarantined stock may be placed in a quarantine bin"
                )

            if bin_obj.bin_type != "QUARANTINE" and status == "QUARANTINE":
                raise ValueError(
                    "Quarantined stock must use a QUARANTINE bin"
                )

    def qty_in_bin(self, bin_id, include_quarantine=True):
        return sum(
            x.qty for x in self.stock.values()
            if x.bin_id == bin_id
            and (include_quarantine or x.status != "QUARANTINE")
        )

    def weight_in_bin(self, bin_id):
        return sum(
            x.qty * self.sku_master.get(x.sku_id, {}).get("unit_weight_kg", 0)
            for x in self.stock.values()
            if x.bin_id == bin_id
        )

    def add_stock(
        self, bin_id, sku_id, lot_no, qty, grn_date=None,
        mfg_date=None, expiry_date=None, status="AVAILABLE",
        timestamp=None, reference=""
    ):
        # Cycle-count corrections are permitted in frozen bins.
        if reference != "CYCLE_COUNT_ADJUSTMENT":
            self._check_not_frozen(bin_id, "stock addition")

        self._validate_location(bin_id, sku_id, qty, status)

        grn_date = grn_date or date.today()
        key = self._key(bin_id, sku_id, lot_no)
        existing = self.stock.get(key)

        if existing:
            if (existing.expiry_date, existing.mfg_date) != (
                expiry_date, mfg_date
            ):
                raise ValueError("Lot dates do not match existing stock record")

            existing.qty += qty
        else:
            self.stock[key] = StockLot(
                bin_id, sku_id, lot_no, qty,
                grn_date, mfg_date, expiry_date, status
            )

        try:
            self._check_capacity(bin_id)
        except Exception:
            if existing:
                existing.qty -= qty
            else:
                self.stock.pop(key, None)
            raise

        movement_type = (
            "ADJUSTMENT"
            if reference == "CYCLE_COUNT_ADJUSTMENT"
            else "RECEIPT"
        )

        self.movements.append(
            Movement(
                timestamp or datetime.now(),
                movement_type,
                sku_id,
                lot_no,
                qty,
                None,
                bin_id,
                reference
            )
        )

        return self.stock[key]

    def _check_capacity(self, bin_id):
        if not self.warehouse:
            return

        b = self.warehouse.get_bin(bin_id)

        if self.qty_in_bin(bin_id) > b.capacity_units:
            raise ValueError(f"Unit capacity exceeded in {bin_id}")

        if self.weight_in_bin(bin_id) > b.max_weight_kg:
            raise ValueError(f"Weight capacity exceeded in {bin_id}")

        skus = {
            x.sku_id for x in self.stock.values()
            if x.bin_id == bin_id and x.qty > 0
        }

        if len(skus) > 2:
            raise ValueError(f"Maximum two SKUs allowed in bin {bin_id}")

    def remove_stock(
        self, bin_id, sku_id, lot_no, qty,
        timestamp=None, reference="", movement_type="PICK"
    ):
        # Cycle-count adjustments are permitted in frozen bins.
        if movement_type != "ADJUSTMENT":
            self._check_not_frozen(bin_id, "stock removal")

        if qty <= 0:
            raise ValueError("Quantity must be positive")

        key = self._key(bin_id, sku_id, lot_no)
        item = self.stock.get(key)

        if (
            not item
            or item.qty < qty
            or item.status not in self.PICKABLE_STATUSES
        ):
            raise ValueError(
                f"Insufficient available stock for {sku_id}/{lot_no} in {bin_id}"
            )

        item.qty -= qty

        if item.qty == 0:
            del self.stock[key]

        self.movements.append(
            Movement(
                timestamp or datetime.now(),
                movement_type,
                sku_id,
                lot_no,
                qty,
                bin_id,
                None,
                reference
            )
        )

    def move_stock(
        self, from_bin, to_bin, sku_id, lot_no, qty,
        timestamp=None, reference="", status=None
    ):
        # Expiry quarantine is allowed to remove stock from a frozen bin,
        # but stock cannot be moved into a frozen bin.
        expiry_quarantine = reference == "EXPIRY_QUARANTINE"

        if not expiry_quarantine:
            self._check_not_frozen(from_bin, "stock transfer")

        self._check_not_frozen(to_bin, "stock transfer")

        if qty <= 0:
            raise ValueError("Quantity must be positive")

        key = self._key(from_bin, sku_id, lot_no)
        source = self.stock.get(key)

        if (
            not source
            or source.qty < qty
            or source.status not in self.PICKABLE_STATUSES
        ):
            raise ValueError("Insufficient source stock")

        destination_status = status if status is not None else source.status
        self._validate_location(to_bin, sku_id, qty, destination_status)

        dest_key = self._key(to_bin, sku_id, lot_no)
        dest_old = self.stock.get(dest_key)
        old_qty = dest_old.qty if dest_old else 0
        old_source_qty = source.qty

        source.qty -= qty

        if source.qty == 0:
            del self.stock[key]

        try:
            if dest_old:
                dest_old.qty += qty
            else:
                self.stock[dest_key] = StockLot(
                    to_bin,
                    sku_id,
                    lot_no,
                    qty,
                    source.grn_date,
                    source.mfg_date,
                    source.expiry_date,
                    destination_status
                )

            self._check_capacity(to_bin)

        except Exception:
            self.stock.pop(dest_key, None)

            if dest_old:
                dest_old.qty = old_qty
                self.stock[dest_key] = dest_old

            source.qty = old_source_qty
            self.stock[key] = source
            raise

        self.movements.append(
            Movement(
                timestamp or datetime.now(),
                "TRANSFER",
                sku_id,
                lot_no,
                qty,
                from_bin,
                to_bin,
                reference
            )
        )

    def on_hand(
        self, sku_id=None, bin_id=None, lot_no=None,
        include_quarantine=False
    ):
        return sum(
            x.qty for x in self.stock.values()
            if (sku_id is None or x.sku_id == sku_id)
            and (bin_id is None or x.bin_id == bin_id)
            and (lot_no is None or x.lot_no == lot_no)
            and (
                include_quarantine
                or x.status in self.PICKABLE_STATUSES
            )
        )

    def available(self, sku_id, lot_no=None):
        return self.on_hand(
            sku_id=sku_id,
            lot_no=lot_no,
            include_quarantine=False
        )

    def lots(self, sku_id=None, bin_id=None, pickable_only=False, as_of=None):
        items = [
            x for x in self.stock.values()
            if (sku_id is None or x.sku_id == sku_id)
            and (bin_id is None or x.bin_id == bin_id)
            and x.status in self.PICKABLE_STATUSES
        ]

        if pickable_only:
            as_of = as_of or date.today()

            if isinstance(as_of, datetime):
                as_of = as_of.date()

            items = [
                x for x in items
                if x.expiry_date is None
                or (x.expiry_date - as_of).days > 7
            ]

        return list(items)

    def refresh_slow_stock(self, as_of):
        """Mark non-expiry-tracked lots older than 90 days as SLOW."""
        if isinstance(as_of, datetime):
            as_of = as_of.date()

        for lot in self.stock.values():
            sku = self.sku_master.get(lot.sku_id, {})
            expiry_tracked = sku.get("expiry_tracked", False)

            age_days = (as_of - lot.grn_date).days

            if (
                not expiry_tracked
                and age_days > 90
                and lot.status == "AVAILABLE"
            ):
                lot.status = "SLOW"

    def set_status(self, bin_id, sku_id, lot_no, status):
        item = self.stock.get(self._key(bin_id, sku_id, lot_no))

        if not item:
            raise ValueError("Stock lot not found")

        item.status = status

    def stock_on_hand_rows(self):
        return [
            {
                "bin_id": x.bin_id,
                "sku_id": x.sku_id,
                "lot_no": x.lot_no,
                "qty": x.qty,
                "status": x.status
            }
            for x in self.stock.values()
        ]
