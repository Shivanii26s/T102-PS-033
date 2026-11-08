
from datetime import datetime

from src.services.inventory import InventoryService


class ReplenishmentService:
    """Move eligible reserve stock to a pick face below 20% capacity."""

    def __init__(
        self,
        inventory,
        warehouse,
        sku_master=None,
        trigger_ratio=0.20,
        target_ratio=0.80
    ):
        self.inventory = inventory
        self.warehouse = warehouse
        self.sku_master = sku_master or inventory.sku_master
        self.trigger_ratio = trigger_ratio
        self.target_ratio = target_ratio

    def _sort_lots(self, lots, expiry_tracked):
        """Use FEFO for expiry SKUs and FIFO for other SKUs."""
        if expiry_tracked:
            return sorted(
                lots,
                key=lambda lot: (
                    lot.expiry_date or datetime.max.date(),
                    lot.bin_id,
                    lot.lot_no
                )
            )

        return sorted(
            lots,
            key=lambda lot: (
                lot.status == "SLOW",
                lot.grn_date,
                lot.bin_id,
                lot.lot_no
            )
        )

    def replenish(self, sku_id, at=None):
        at = at or datetime.now()

        sku = self.sku_master.get(sku_id)
        if not sku:
            raise ValueError(f"Unknown SKU: {sku_id}")

        pick_bin = sku.get("pick_face_bin")
        if not pick_bin:
            raise ValueError(
                f"No pick-face bin configured for {sku_id}"
            )

        bin_obj = self.warehouse.get_bin(pick_bin)

        if bin_obj.bin_type != "PICK_FACE":
            raise ValueError(
                f"Configured bin {pick_bin} is not a PICK_FACE"
            )

        capacity = bin_obj.capacity_units
        current = self.inventory.on_hand(
            sku_id=sku_id,
            bin_id=pick_bin
        )

        if pick_bin in self.inventory.frozen_bins:
            return {
                "status": "FROZEN_PICK_FACE",
                "moved_qty": 0,
                "pick_face_qty": current
            }

        if current >= capacity * self.trigger_ratio:
            return {
                "status": "NOT_REQUIRED",
                "moved_qty": 0,
                "pick_face_qty": current
            }

        target = int(capacity * self.target_ratio)
        requested = max(0, target - current)
        unit_weight = sku["unit_weight_kg"]
        units_left = capacity - self.inventory.qty_in_bin(pick_bin)
        weight_left = (
            bin_obj.max_weight_kg - self.inventory.weight_in_bin(pick_bin)
        )
        weight_units_left = int(weight_left // unit_weight)
        destination_capacity = max(0, min(units_left, weight_units_left))
        needed = min(requested, destination_capacity)

        reserve_bins = self.warehouse.compatible_bins(
            sku["temp_class"],
            {"RESERVE"}
        )
        reserve_ids = {b.bin_id for b in reserve_bins}

        # inventory.lots() returns only AVAILABLE and SLOW lots.
        # QUARANTINE stock is therefore excluded.
        lots = [
            lot
            for lot in self.inventory.lots(sku_id=sku_id)
            if lot.bin_id in reserve_ids
            and lot.bin_id not in self.inventory.frozen_bins
            and lot.status in InventoryService.PICKABLE_STATUSES
        ]

        lots = self._sort_lots(
            lots,
            sku.get("expiry_tracked", False)
        )

        moved = 0

        for lot in lots:
            qty = min(needed - moved, lot.qty)

            if qty <= 0:
                break

            self.inventory.move_stock(
                lot.bin_id,
                pick_bin,
                sku_id,
                lot.lot_no,
                qty,
                timestamp=at,
                reference="PICK_FACE_REPLENISHMENT"
            )

            moved += qty

            if moved >= needed:
                break

        return {
            "status": "REPLENISHED" if moved else "NO_RESERVE_STOCK",
            "moved_qty": moved,
            "pick_face_qty": current + moved,
            "target_qty": target,
            "short_qty": max(0, requested - moved)
        }
