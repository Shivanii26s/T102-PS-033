import csv
from datetime import datetime


class AuditService:
    """Movement log, stock snapshot export and cycle-count variance decisions."""
    def __init__(self, inventory):
        self.inventory = inventory
        self.events = []

    def record(self, event_type, reference="", details=None, timestamp=None):
        event = {"timestamp": timestamp or datetime.now(), "event_type": event_type,
                 "reference": reference, "details": details or {}}
        self.events.append(event)
        return event

    def movement_rows(self):
        return [{"timestamp": m.timestamp.isoformat(sep=" "), "movement_type": m.movement_type,
                 "sku_id": m.sku_id, "lot_no": m.lot_no, "qty": m.qty,
                 "from_bin": m.from_bin or "", "to_bin": m.to_bin or "",
                 "reference": m.reference, "note": m.note} for m in self.inventory.movements]

    def export_movements(self, file_path):
        rows = self.movement_rows()
        fields = ["timestamp", "movement_type", "sku_id", "lot_no", "qty", "from_bin", "to_bin", "reference", "note"]
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
        freeze = abs(variance) > threshold
        return {"system_qty": system_qty, "counted_qty": counted_qty,
                "variance": variance, "freeze_required": freeze}

    def apply_adjustment(self, inventory, bin_id, sku_id, lot_no, counted_qty,
                         grn_date=None, timestamp=None):
        key = (bin_id, sku_id, lot_no)
        current = inventory.stock.get(key)
        system_qty = current.qty if current else 0
        result = self.count_variance(system_qty, counted_qty)
        if counted_qty == system_qty:
            return result
        if counted_qty < system_qty:
            # The caller should supply lot-specific count rows; this reduces this lot.
            inventory.remove_stock(bin_id, sku_id, lot_no, system_qty - counted_qty,
                                   timestamp=timestamp, reference="CYCLE_COUNT_ADJUSTMENT",
                                   movement_type="ADJUSTMENT")
        else:
            inventory.add_stock(bin_id, sku_id, lot_no, counted_qty - system_qty,
                                grn_date=grn_date, timestamp=timestamp,
                                reference="CYCLE_COUNT_ADJUSTMENT")
        self.record("ADJUSTMENT", "CYCLE_COUNT", {**result, "bin_id": bin_id, "sku_id": sku_id}, timestamp)
        return result
