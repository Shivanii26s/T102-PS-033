from datetime import datetime


class ReplenishmentService:
    """Moves oldest eligible reserve lots to a pick face when it falls below 20%."""
    def __init__(self, inventory, warehouse, sku_master=None, trigger_ratio=0.20, target_ratio=0.80):
        self.inventory = inventory
        self.warehouse = warehouse
        self.sku_master = sku_master or inventory.sku_master
        self.trigger_ratio = trigger_ratio
        self.target_ratio = target_ratio

    def replenish(self, sku_id, at=None):
        at = at or datetime.now()
        sku = self.sku_master.get(sku_id)
        if not sku:
            raise ValueError(f"Unknown SKU: {sku_id}")
        pick_bin = sku.get("pick_face_bin")
        if not pick_bin:
            raise ValueError(f"No pick-face bin configured for {sku_id}")
        bin_obj = self.warehouse.get_bin(pick_bin)
        if bin_obj.bin_type != "PICK_FACE":
            raise ValueError(f"Configured bin {pick_bin} is not a PICK_FACE")
        capacity = bin_obj.capacity_units
        current = self.inventory.on_hand(sku_id=sku_id, bin_id=pick_bin)
        if current >= capacity * self.trigger_ratio:
            return {"status": "NOT_REQUIRED", "moved_qty": 0, "pick_face_qty": current}
        target = int(capacity * self.target_ratio)
        needed = max(0, target - current)
        reserve_bins = [b for b in self.warehouse.compatible_bins(sku["temp_class"], {"RESERVE"})]
        reserve_ids = {b.bin_id for b in reserve_bins}
        lots = [x for x in self.inventory.lots(sku_id=sku_id) if x.bin_id in reserve_ids]
        lots.sort(key=lambda x: (x.grn_date, x.bin_id, x.lot_no))
        moved = 0
        for lot in lots:
            qty = min(needed - moved, lot.qty)
            if qty <= 0:
                break
            self.inventory.move_stock(lot.bin_id, pick_bin, sku_id, lot.lot_no, qty,
                                      timestamp=at, reference="PICK_FACE_REPLENISHMENT")
            moved += qty
            if moved >= needed:
                break
        return {"status": "REPLENISHED" if moved else "NO_RESERVE_STOCK",
                "moved_qty": moved, "pick_face_qty": current + moved,
                "target_qty": target, "short_qty": max(0, needed - moved)}
