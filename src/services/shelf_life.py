from datetime import date, datetime


class ShelfLifeService:
    """Applies the minimum shelf-life and slow-moving stock rules."""

    def __init__(
        self,
        inventory,
        sku_master=None,
        minimum_shelf_life_days=60,
        slow_moving_days=90,
    ):
        if minimum_shelf_life_days < 0:
            raise ValueError("Minimum shelf life cannot be negative")
        if slow_moving_days < 0:
            raise ValueError("Slow-moving threshold cannot be negative")

        self.inventory = inventory
        self.sku_master = sku_master or inventory.sku_master
        self.minimum_shelf_life_days = minimum_shelf_life_days
        self.slow_moving_days = slow_moving_days

    @staticmethod
    def _as_date(value):
        return value.date() if isinstance(value, datetime) else value

    def is_pickable(self, lot, as_of, minimum_shelf_life_days=None):
        """Return whether a lot meets the applicable minimum remaining life."""
        if lot.expiry_date is None:
            return True

        as_of = self._as_date(as_of)
        minimum_days = (
            self.minimum_shelf_life_days
            if minimum_shelf_life_days is None
            else minimum_shelf_life_days
        )
        if minimum_days < 0:
            raise ValueError("Minimum shelf life cannot be negative")
        return (lot.expiry_date - as_of).days >= minimum_days

    def is_slow_moving(self, lot, as_of):
        """A lot becomes slow-moving only after more than 90 days in stock."""
        as_of = self._as_date(as_of)
        return (as_of - lot.grn_date).days > self.slow_moving_days

    def get_pickable_lots(
        self, sku_id, as_of=None, minimum_shelf_life_days=None
    ):
        """Return eligible lots in FEFO/FIFO order, with slow FIFO lots last."""
        as_of = self._as_date(as_of or date.today())
        sku = self.sku_master.get(sku_id)
        if sku is None:
            raise ValueError(f"Unknown SKU: {sku_id}")

        lots = self.inventory.lots(sku_id=sku_id, pickable_only=False)
        if sku.get("expiry_tracked", False):
            lots = [
                lot for lot in lots
                if lot.expiry_date is not None
                and self.is_pickable(lot, as_of, minimum_shelf_life_days)
            ]
            lots.sort(key=lambda lot: (lot.expiry_date, lot.bin_id))
        else:
            lots.sort(
                key=lambda lot: (
                    self.is_slow_moving(lot, as_of),
                    lot.grn_date,
                    lot.bin_id,
                )
            )
        return lots
