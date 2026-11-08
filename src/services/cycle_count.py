from datetime import date, datetime

from src.services.audit import AuditService


class CycleCountService:
    """Validates cycle counts, freezes discrepant bins, and posts adjustments."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.pending_counts = {}

    @staticmethod
    def validate_count(system_qty, counted_qty):
        return AuditService.count_variance(system_qty, counted_qty)

    def apply_count(
        self, bin_id, sku_id, counted_qty, lot_no=None, timestamp=None
    ):
        """Record a SKU total for a bin; defer frozen-bin adjustments."""
        timestamp = self._as_timestamp(timestamp)
        system_qty = self.inventory.on_hand(sku_id=sku_id, bin_id=bin_id)
        result = self.validate_count(system_qty, counted_qty)
        if counted_qty == system_qty:
            self.pending_counts.get(bin_id, {}).pop(sku_id, None)
            return result

        if result["freeze_required"] or bin_id in self.inventory.frozen_bins:
            self.inventory.frozen_bins.add(bin_id)
            self.pending_counts.setdefault(bin_id, {})[sku_id] = {
                "counted_qty": counted_qty,
                "lot_no": lot_no,
                "timestamp": timestamp,
            }
            return result

        self._adjust_sku_count(
            bin_id, sku_id, counted_qty, lot_no, timestamp
        )
        return result

    def adjust_bin(self, bin_id, timestamp=None):
        """Post queued counts for a frozen bin, then unfreeze it."""
        if bin_id not in self.inventory.frozen_bins:
            raise ValueError(f"Bin is not frozen: {bin_id}")
        timestamp = self._as_timestamp(timestamp)

        counts = self.pending_counts.get(bin_id, {})
        for sku_id, count in counts.items():
            self._adjust_sku_count(
                bin_id,
                sku_id,
                count["counted_qty"],
                count["lot_no"],
                timestamp or count["timestamp"],
            )

        self.pending_counts.pop(bin_id, None)
        self.inventory.frozen_bins.remove(bin_id)
        return True

    @staticmethod
    def _as_timestamp(value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        return value

    def _adjust_sku_count(
        self, bin_id, sku_id, counted_qty, lot_no, timestamp
    ):
        system_qty = self.inventory.on_hand(sku_id=sku_id, bin_id=bin_id)
        difference = counted_qty - system_qty
        if difference == 0:
            return

        if difference < 0:
            remaining = -difference
            lots = sorted(
                self.inventory.lots(sku_id=sku_id, bin_id=bin_id),
                key=lambda lot: (lot.grn_date, lot.lot_no),
            )
            for lot in lots:
                adjustment_qty = min(remaining, lot.qty)
                self.inventory.remove_stock(
                    bin_id,
                    sku_id,
                    lot.lot_no,
                    adjustment_qty,
                    timestamp=timestamp,
                    reference="CYCLE_COUNT_ADJUSTMENT",
                    movement_type="ADJUSTMENT",
                )
                remaining -= adjustment_qty
                if remaining == 0:
                    break
            if remaining:
                raise ValueError(
                    f"Insufficient available stock to adjust {sku_id} in {bin_id}"
                )
            return

        if not lot_no:
            raise ValueError(
                "lot_no is required for a positive stock adjustment"
            )

        key = (bin_id, sku_id, lot_no)
        existing = self.inventory.stock.get(key)
        if existing and existing.status != "AVAILABLE":
            raise ValueError(
                f"Cannot adjust non-available lot {sku_id}/{lot_no} in {bin_id}"
            )
        if isinstance(timestamp, datetime):
            grn_date = timestamp.date()
        elif isinstance(timestamp, date):
            grn_date = timestamp
        else:
            grn_date = None

        self.inventory.add_stock(
            bin_id,
            sku_id,
            lot_no,
            difference,
            grn_date=existing.grn_date if existing else grn_date,
            mfg_date=existing.mfg_date if existing else None,
            expiry_date=existing.expiry_date if existing else None,
            timestamp=timestamp if isinstance(timestamp, datetime) else None,
            reference="CYCLE_COUNT_ADJUSTMENT",
        )
