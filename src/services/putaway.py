
from datetime import date, datetime


class PutawayService:
    """Selects warehouse bins and records GRN stock putaway."""

    MIN_SPLIT_REMAINDER = 10
    QUARANTINE_DAYS = 30

    def __init__(self, warehouse, inventory, sku_master=None):
        self.warehouse = warehouse
        self.inventory = inventory
        self.sku_master = sku_master or inventory.sku_master

    def _available_capacity(self, bin_obj, sku_id):
        """Return the maximum additional units that can fit in a bin."""
        sku = self.sku_master[sku_id]
        unit_weight = sku["unit_weight_kg"]

        units_left = bin_obj.capacity_units - self.inventory.qty_in_bin(
            bin_obj.bin_id
        )
        weight_left = bin_obj.max_weight_kg - self.inventory.weight_in_bin(
            bin_obj.bin_id
        )

        weight_units_left = int(weight_left // unit_weight)
        return max(0, min(units_left, weight_units_left))

    def _bin_has_sku_lot(self, bin_id, sku_id, lot_no):
        item = self.inventory.stock.get((bin_id, sku_id, lot_no))
        return item is not None and item.qty > 0 and item.status == "AVAILABLE"

    def _bin_skus(self, bin_id):
        return {
            item.sku_id
            for item in self.inventory.stock.values()
            if item.bin_id == bin_id and item.qty > 0
        }

    def _can_accept_sku(self, bin_obj, sku_id, lot_no):
        if bin_obj.bin_type == "QUARANTINE":
            return False

        if bin_obj.temp_class != self.sku_master[sku_id]["temp_class"]:
            return False

        existing_skus = self._bin_skus(bin_obj.bin_id)

        if sku_id not in existing_skus and len(existing_skus) >= 2:
            return False

        return self._available_capacity(bin_obj, sku_id) > 0

    def _normal_candidates(self, sku_id, lot_no):
        sku = self.sku_master[sku_id]
        compatible = self.warehouse.compatible_bins(
            sku["temp_class"],
            {"PICK_FACE", "RESERVE"}
        )

        # Priority 1: bins already containing this SKU and lot.
        same_lot = [
            b for b in compatible
            if self._bin_has_sku_lot(b.bin_id, sku_id, lot_no)
            and self._can_accept_sku(b, sku_id, lot_no)
        ]

        # Priority 2: empty bins in the SKU's home zone.
        home_zone = [
            b for b in compatible
            if b.zone_id == sku["home_zone"]
            and self.inventory.qty_in_bin(b.bin_id) == 0
            and self._can_accept_sku(b, sku_id, lot_no)
        ]

        # Priority 3: any other empty, temperature-compatible bin.
        other_empty = [
            b for b in compatible
            if self.inventory.qty_in_bin(b.bin_id) == 0
            and b.zone_id != sku["home_zone"]
            and self._can_accept_sku(b, sku_id, lot_no)
        ]

        return [
            (1, same_lot),
            (2, home_zone),
            (3, other_empty),
        ]

    def _quarantine_candidates(self, sku_id):
        temp_class = self.sku_master[sku_id]["temp_class"]

        return sorted(
            self.warehouse.compatible_bins(
                temp_class, {"QUARANTINE"}
            ),
            key=lambda b: (b.aisle, b.bin_no, b.bin_id)
        )

    def putaway_line(self, grn_line, at_datetime=None):
        """Put away one validated GRN line and return its output rows."""
        at_datetime = at_datetime or grn_line.grn_ts
        if isinstance(at_datetime, datetime):
            as_of = at_datetime.date()
        else:
            as_of = at_datetime

        sku_id = grn_line.sku_id
        lot_no = grn_line.lot_no
        remaining = grn_line.qty

        if sku_id not in self.sku_master:
            raise ValueError(f"Unknown SKU: {sku_id}")

        sku = self.sku_master[sku_id]

        # Expiry within 30 days is routed to quarantine.
        expiry_soon = (
            grn_line.expiry_date is not None
            and (grn_line.expiry_date - as_of).days <= self.QUARANTINE_DAYS
        )

        if expiry_soon:
            candidates = [(4, self._quarantine_candidates(sku_id))]
        else:
            candidates = self._normal_candidates(sku_id, lot_no)

        output_rows = []

        for precedence_step, bins in candidates:
            bins = sorted(
                bins,
                key=lambda b: (b.aisle, b.bin_no, b.bin_id)
            )

            for bin_obj in bins:
                if remaining <= 0:
                    break

                capacity = self._available_capacity(bin_obj, sku_id)

                if capacity <= 0:
                    continue

                # Do not split if the leftover would be fewer than 10 units.
                if capacity < remaining and remaining - capacity < self.MIN_SPLIT_REMAINDER:
                    continue

                put_qty = min(remaining, capacity)

                status = (
                    "QUARANTINE"
                    if bin_obj.bin_type == "QUARANTINE"
                    else "AVAILABLE"
                )

                self.inventory.add_stock(
                    bin_id=bin_obj.bin_id,
                    sku_id=sku_id,
                    lot_no=lot_no,
                    qty=put_qty,
                    grn_date=grn_line.grn_ts.date(),
                    mfg_date=grn_line.mfg_date,
                    expiry_date=grn_line.expiry_date,
                    status=status,
                    timestamp=grn_line.grn_ts,
                    reference=grn_line.grn_id,
                )

                output_rows.append({
                    "grn_id": grn_line.grn_id,
                    "line_no": grn_line.line_no,
                    "sku_id": sku_id,
                    "lot_no": lot_no,
                    "bin_id": bin_obj.bin_id,
                    "qty": put_qty,
                    "precedence_step": precedence_step,
                    "rule_ids": f"PUTAWAY_{precedence_step}",
                })

                remaining -= put_qty

            if remaining <= 0:
                break

        if remaining > 0:
            raise ValueError(
                f"Could not put away {remaining} units of "
                f"{sku_id}/{lot_no}: insufficient compatible bin capacity"
            )

        return output_rows
