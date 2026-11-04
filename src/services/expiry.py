from datetime import date, datetime, time


class ExpiryService:
    """Applies the seven-day pick block and end-of-day quarantine rule."""
    def __init__(self, inventory, warehouse=None):
        self.inventory = inventory
        self.warehouse = warehouse

    @staticmethod
    def is_pickable(expiry_date, at):
        if expiry_date is None:
            return True
        current_date = at.date() if isinstance(at, datetime) else at
        return (expiry_date - current_date).days > 7

    def blocked_lots(self, as_of):
        current_date = as_of.date() if isinstance(as_of, datetime) else as_of
        return [x for x in self.inventory.stock.values() if x.status == "AVAILABLE"
                and x.expiry_date is not None and not self.is_pickable(x.expiry_date, current_date)]

    def quarantine_due(self, as_of, quarantine_bin_by_temp=None):
        """At EOD, move lots with <=7 days remaining into compatible quarantine bins.
        Pass {temp_class: quarantine_bin_id}; without a mapping, mark status QUARANTINE in place.
        """
        current_date = as_of.date() if isinstance(as_of, datetime) else as_of
        if isinstance(as_of, datetime) and as_of.time() < time(23, 59, 59):
            raise ValueError("Quarantine processing is only permitted at end of day")
        changed = []
        for item in list(self.blocked_lots(current_date)):
            if quarantine_bin_by_temp and self.warehouse:
                sku = self.inventory.sku_master.get(item.sku_id, {})
                temp = sku.get("temp_class")
                target = quarantine_bin_by_temp.get(temp)
                if not target:
                    continue
                self.inventory.move_stock(item.bin_id, target, item.sku_id, item.lot_no,
                                           item.qty, timestamp=datetime.combine(current_date, time(23, 59, 59)),
                                           reference="EXPIRY_QUARANTINE", status="QUARANTINE")
            else:
                item.status = "QUARANTINE"
            changed.append((item.sku_id, item.lot_no))
        return changed
