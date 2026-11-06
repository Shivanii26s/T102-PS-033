
from datetime import date, datetime, timedelta


class PickingService:
    """Selects stock lots for picking using FEFO or FIFO."""

    def __init__(self, inventory, sku_master, minimum_shelf_life_days=60):
        self.inventory = inventory
        self.sku_master = sku_master
        self.minimum_shelf_life_days = minimum_shelf_life_days

    def get_pickable_lots(self, sku_id, as_of=None):
        as_of = as_of or date.today()
        if isinstance(as_of, datetime):
            as_of = as_of.date()

        sku = self.sku_master.get(sku_id)
        if not sku:
            raise ValueError(f"Unknown SKU: {sku_id}")

        expiry_tracked = sku.get("expiry_tracked", False)
        lots = self.inventory.lots(
            sku_id=sku_id,
            pickable_only=False,
            as_of=as_of
        )

        # Exclude lots that do not meet the minimum shelf-life rule.
        if expiry_tracked:
            minimum_expiry = as_of + timedelta(
                days=self.minimum_shelf_life_days
            )
            lots = [
                lot for lot in lots
                if lot.expiry_date is not None
                and lot.expiry_date >= minimum_expiry
            ]

        if expiry_tracked:
            # FEFO: earliest expiry first; bin ID breaks ties.
            lots.sort(key=lambda lot: (
                lot.expiry_date,
                lot.bin_id
            ))
        else:
            # FIFO: oldest GRN first.
            # Stock received more than 90 days ago goes to the back.
            lots.sort(key=lambda lot: (
                (as_of - lot.grn_date).days > 90,
                lot.grn_date,
                lot.bin_id
            ))

        return lots

    def create_pick_list(self, sku_id, requested_qty, as_of=None):
        if requested_qty <= 0:
            raise ValueError("Requested quantity must be positive")

        lots = self.get_pickable_lots(sku_id, as_of)
        remaining = requested_qty
        allocations = []

        for lot in lots:
            if remaining <= 0:
                break

            pick_qty = min(lot.qty, remaining)
            allocations.append({
                "sku_id": sku_id,
                "lot_no": lot.lot_no,
                "bin_id": lot.bin_id,
                "qty": pick_qty
            })
            remaining -= pick_qty

        if remaining > 0:
            raise ValueError(
                f"Insufficient pickable stock for {sku_id}. "
                f"Short by {remaining} units."
            )

        return allocations

    def confirm_pick(self, allocations, timestamp=None, reference=""):
        """Deduct stock only after the pick list is confirmed."""
        for item in allocations:
            self.inventory.remove_stock(
                item["bin_id"],
                item["sku_id"],
                item["lot_no"],
                item["qty"],
                timestamp=timestamp,
                reference=reference,
                movement_type="PICK"
            )

        return True
