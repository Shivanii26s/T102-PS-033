from datetime import date, datetime, timedelta

import pytest

from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def setup_br06():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)
    inv.add_stock(
        "B1", "SKU1", "LOT1", 8,
        date(2028, 1, 1)
    )

    return inv, sku


def test_br06_reservation_active_before_48_hours():
    inv, sku = setup_br06()
    svc = ReservationService(inv, sku)

    start = datetime(2028, 2, 1, 10, 0)
    reservations = svc.reserve_order(
        "O1", {"SKU1": 2}, start
    )

    released = svc.release_expired(
        start + timedelta(hours=48) - timedelta(seconds=1)
    )

    assert len(reservations) == 1
    assert released == []
    assert reservations[0].released is False


def test_br06_reservation_expires_at_exactly_48_hours():
    inv, sku = setup_br06()
    svc = ReservationService(inv, sku)

    start = datetime(2028, 2, 1, 10, 0)
    reservations = svc.reserve_order(
        "O1", {"SKU1": 2}, start
    )

    released = svc.release_expired(
        start + timedelta(hours=48)
    )

    assert len(released) == 1
    assert reservations[0].released is True


def test_br06_reservation_is_released_after_48_hours():
    inv, sku = setup_br06()
    svc = ReservationService(inv, sku)

    start = datetime(2028, 2, 1, 10, 0)
    reservations = svc.reserve_order(
        "O1", {"SKU1": 2}, start
    )

    released = svc.release_expired(
        start + timedelta(hours=48, seconds=1)
    )

    assert len(released) == 1
    assert reservations[0].released is True


def test_br06_confirmation_at_exact_48_hours_is_rejected():
    inv, sku = setup_br06()
    svc = ReservationService(inv, sku)

    start = datetime(2028, 2, 1, 10, 0)
    svc.reserve_order("O1", {"SKU1": 2}, start)

    with pytest.raises(ValueError, match="expired"):
        svc.confirm_order(
            "O1", start + timedelta(hours=48)
        )


def test_br06_confirmed_reservation_stays_locked_after_48_hours():
    inv, sku = setup_br06()
    svc = ReservationService(inv, sku)

    start = datetime(2028, 2, 1, 10, 0)

    svc.reserve_order("O1", {"SKU1": 5}, start)
    svc.confirm_order("O1", start + timedelta(hours=1))

    later = start + timedelta(hours=49)

    second_order = svc.reserve_order(
        "O2", {"SKU1": 3}, later
    )

    assert sum(r.qty for r in second_order) == 3

    third_order = svc.reserve_order(
        "O3", {"SKU1": 1}, later
    )

    assert third_order == []
    assert svc.orders["O3"]["status"] == "HOLD"
