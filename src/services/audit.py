import csv
from datetime import date, datetime


class AuditService:
    """Movement log, stock snapshot export and cycle-count variance decisions."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.events = []

    def record(self, event_type, reference="", details=None, timestamp=None):
        event = {
            "timestamp": timestamp or datetime.now(),
            "event_type": event_type,
            "reference": reference,
            "details": details or {}
        }
        self.events.append(event)
        return event

    def movement_rows(self):
        return [
            {
                "timestamp": m.timestamp.isoformat(sep=" "),
                "movement_type": m.movement_type,
                "sku_id": m.sku_id,
                "lot_no": m.lot_no,
                "qty": m.qty,
                "from_bin": m.from_bin or "",
                "to_bin": m.to_bin or "",
                "reference": m.reference,
                "note": m.note
            }
            for m in self.inventory.movements
        ]

    def export_movements(self, file_path):
        rows = self.movement_rows()
        fields = [
            "timestamp", "movement_type", "sku_id", "lot_no",
            "qty", "from_bin", "to_bin", "reference", "note"
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        return len(rows)

    def stock_snapshot(self):
        return self.inventory.stock_on_hand_rows()

    def export_stock_on_hand(self, file_path):
        rows = self.stock_snapshot()
        fields = ["bin_id", "sku_id", "lot_no", "qty", "status"]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        return len(rows)

    @staticmethod
    def count_variance(system_qty, counted_qty):
        if system_qty < 0 or counted_qty < 0:
            raise ValueError("Stock quantities cannot be negative")

        variance = counted_qty - system_qty
        threshold = min(0.02 * system_qty, 5)

        return {
            "system_qty": system_qty,
            "counted_qty": counted_qty,
            "variance": variance,
            "freeze_required": abs(variance) > threshold
        }

    def apply_adjustment(
        self,
        inventory,
        bin_id,
        sku_id,
        lot_no,
        counted_qty,
        grn_date=None,
        timestamp=None
    ):
        # Count all eligible lots for this SKU in this bin.
        lots = [
            lot for lot in inventory.stock.values()
            if lot.bin_id == bin_id
            and lot.sku_id == sku_id
            and lot.status in inventory.PICKABLE_STATUSES
        ]

        system_qty = sum(lot.qty for lot in lots)

        result = self.count_variance(system_qty, counted_qty)

        if result["freeze_required"]:
            inventory.frozen_bins.add(bin_id)

        difference = counted_qty - system_qty

        if difference == 0:
            return result

        if difference < 0:
            # Reduce the oldest GRN lot first.
            shortage = abs(difference)

            lots.sort(
                key=lambda lot: (
                    lot.grn_date,
                    lot.bin_id,
                    lot.lot_no
                )
            )

            for lot in lots:
                if shortage <= 0:
                    break

                reduction = min(shortage, lot.qty)

                inventory.remove_stock(
                    lot.bin_id,
                    lot.sku_id,
                    lot.lot_no,
                    reduction,
                    timestamp=timestamp,
                    reference="CYCLE_COUNT_ADJUSTMENT",
                    movement_type="ADJUSTMENT"
                )

                shortage -= reduction

        else:
            # Add excess counted stock to the specified lot.
            existing = inventory.stock.get(
                (bin_id, sku_id, lot_no)
            )

            if existing:
                adjustment_grn_date = existing.grn_date
                mfg_date = existing.mfg_date
                expiry_date = existing.expiry_date
            else:
                adjustment_grn_date = grn_date or date.today()
                mfg_date = None
                expiry_date = None

            inventory.add_stock(
                bin_id,
                sku_id,
                lot_no,
                difference,
                grn_date=adjustment_grn_date,
                mfg_date=mfg_date,
                expiry_date=expiry_date,
                timestamp=timestamp,
                reference="CYCLE_COUNT_ADJUSTMENT"
            )

            # Record this receipt as an adjustment.
            inventory.movements[-1].movement_type = "ADJUSTMENT"

        self.record(
            "ADJUSTMENT",
            "CYCLE_COUNT",
            {
                **result,
                "bin_id": bin_id,
                "sku_id": sku_id
            },
            timestamp
        )

        return result