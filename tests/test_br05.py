from datetime import date, datetime

from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def make_service(expiry_date):
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": True
        }
    }

    inventory = InventoryService(sku_master=sku)

    inventory.add_stock(
        "B1",
        "SKU1",
        "LOT1",
        10,
        date(2028, 1, 1),
        expiry_date=expiry_date
    )

    return ReservationService(inventory, sku)


def test_br05_exactly_60_days_remaining_is_eligible():
    service = make_service(date(2028, 3, 31))

    result = service.reserve_order(
        "O1",
        {"SKU1": 5},
        datetime(2028, 1, 31)
    )

    assert len(result) == 1
    assert result[0].qty == 5


def test_br05_59_days_remaining_is_not_eligible():
    service = make_service(date(2028, 3, 30))

    result = service.reserve_order(
        "O1",
        {"SKU1": 5},
        datetime(2028, 1, 31)
    )

    assert result == []
    assert service.orders["O1"]["status"] == "HOLD"


def test_br05_expiry_tracked_lot_without_expiry_is_not_eligible():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": True
        }
    }
    inventory = InventoryService(sku_master=sku)
    inventory.add_stock("B1", "SKU1", "LOT1", 10, date(2028, 1, 1))
    service = ReservationService(inventory, sku)

    result = service.reserve_order(
        "O1", {"SKU1": 5}, datetime(2028, 1, 31)
    )

    assert result == []
    assert service.orders["O1"]["status"] == "HOLD"


def test_br05_short_order_uses_only_eligible_stock():
    service = make_service(date(2028, 3, 30))

    result = service.reserve_order(
        "O1",
        {"SKU1": 5},
        datetime(2028, 1, 31),
        allow_short=True
    )

    assert result == []
    assert service.orders["O1"]["status"] == "PARTIAL"