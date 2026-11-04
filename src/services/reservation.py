from datetime import datetime, timedelta

from src.models.entities import Reservation


class ReservationService:
    """Reserves available lots using FEFO/FIFO picking rules."""

    def __init__(
        self,
        inventory,
        sku_master=None,
        lock_hours=48,
        min_shelf_life_days=60
    ):
        self.inventory = inventory
        self.sku_master = sku_master or inventory.sku_master
        self.lock_hours = lock_hours
        self.min_shelf_life_days = min_shelf_life_days
        self.reservations: list[Reservation] = []
        self.orders = {}

    def _reserved_qty(self, bin_id, sku_id, lot_no, at):
        return sum(
            r.qty for r in self.reservations
            if r.bin_id == bin_id
            and r.sku_id == sku_id
            and r.lot_no == lot_no
            and not r.released
            and (r.confirmed or r.expires_at > at)
        )

    def _sort_lots(self, lots, expiry_tracked):
        """Apply FEFO or FIFO, with SLOW stock last for FIFO."""
        if expiry_tracked:
            return sorted(
                lots,
                key=lambda lot: (
                    lot.expiry_date or datetime.max.date(),
                    lot.bin_id
                )
            )

        return sorted(
            lots,
            key=lambda lot: (
                lot.status == "SLOW",
                lot.grn_date,
                lot.bin_id
            )
        )

    def _meets_shelf_life(self, lot, at):
        """Check the minimum remaining shelf life for expiry-tracked stock."""
        if lot.expiry_date is None:
            return False

        current_date = at.date() if isinstance(at, datetime) else at
        remaining_days = (lot.expiry_date - current_date).days

        return remaining_days >= self.min_shelf_life_days

    def release_expired(self, at):
        released = []

        for r in self.reservations:
            if (
                not r.released
                and not r.confirmed
                and r.expires_at <= at
            ):
                r.released = True
                released.append(r)

        return released

    def reserve_order(self, order_id, lines, at, allow_short=False):
        self.release_expired(at)

        if order_id in self.orders:
            raise ValueError(f"Duplicate order: {order_id}")

        plan = []

        for sku_id, requested in lines.items():
            if requested <= 0:
                raise ValueError(
                    f"Order quantity must be positive for {sku_id}"
                )

            sku = self.sku_master.get(sku_id, {})
            expiry_tracked = sku.get("expiry_tracked", False)

            lots = self.inventory.lots(
                sku_id=sku_id,
                pickable_only=True,
                as_of=at
            )

            lots = [
                lot for lot in lots
                if lot.status in self.inventory.PICKABLE_STATUSES
            ]

            if expiry_tracked:
                lots = [
                    lot for lot in lots
                    if self._meets_shelf_life(lot, at)
                ]

            lots = self._sort_lots(lots, expiry_tracked)

            remaining = requested

            for lot in lots:
                free = lot.qty - self._reserved_qty(
                    lot.bin_id, sku_id, lot.lot_no, at
                )

                take = min(remaining, max(0, free))

                if take:
                    plan.append((sku_id, lot, take))
                    remaining -= take

                if remaining == 0:
                    break

            if remaining and not allow_short:
                self.orders[order_id] = {
                    "status": "HOLD",
                    "reservations": []
                }
                return []

        reservations = []

        for sku_id, lot, qty in plan:
            reservation = Reservation(
                order_id,
                sku_id,
                lot.lot_no,
                lot.bin_id,
                qty,
                at,
                at + timedelta(hours=self.lock_hours)
            )

            self.reservations.append(reservation)
            reservations.append(reservation)

        is_partial = any(
            sum(
                r.qty for r in reservations
                if r.sku_id == sku_id
            ) < requested
            for sku_id, requested in lines.items()
        )

        self.orders[order_id] = {
            "status": "PARTIAL" if is_partial else "RESERVED",
            "reservations": reservations
        }

        return reservations

    def confirm_order(self, order_id, at=None):
        record = self.orders.get(order_id)

        if not record or record["status"] == "HOLD":
            raise ValueError(
                f"No active reservation for order {order_id}"
            )

        at = at or datetime.now()

        active = [
            r for r in record["reservations"]
            if not r.released and r.expires_at > at
        ]

        if not active:
            raise ValueError("Reservation has expired")

        for r in active:
            r.confirmed = True

        record["status"] = "CONFIRMED"

        return active

    def release_order(self, order_id):
        record = self.orders.get(order_id)

        if not record:
            return []

        released = []

        for r in record["reservations"]:
            if not r.released:
                r.released = True
                released.append(r)

        record["status"] = "RELEASED"

        return released