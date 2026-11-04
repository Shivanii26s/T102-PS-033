from datetime import date, datetime

from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def setup_br08():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        },
        "SKU2": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock("B1", "SKU1", "LOT1", 5, date(2028, 1, 1))
    inv.add_stock("B2", "SKU1", "LOT2", 8, date(2028, 1, 2))
    inv.add_stock("B3", "SKU2", "LOT3", 3, date(2028, 1, 1))

    svc = ReservationService(inv, sku)

    return inv, svc


def test_br08_allow_short_reserves_available_quantity():
    inv, svc = setup_br08()

    result = svc.reserve_order(
        "O1",
        {"SKU1": 99},
        datetime(2028, 1, 10),
        allow_short=True
    )

    assert sum(r.qty for r in result) == 13
    assert svc.orders["O1"]["status"] == "PARTIAL"


def test_br08_without_allow_short_holds_entire_order():
    inv, svc = setup_br08()

    result = svc.reserve_order(
        "O1",
        {"SKU1": 99},
        datetime(2028, 1, 10),
        allow_short=False
    )

    assert result == []
    assert svc.orders["O1"]["status"] == "HOLD"
    assert svc.reservations == []


def test_br08_multiline_order_holds_everything_if_one_line_is_short():
    inv, svc = setup_br08()

    result = svc.reserve_order(
        "O1",
        {"SKU1": 2, "SKU2": 4},
        datetime(2028, 1, 10),
        allow_short=False
    )

    assert result == []
    assert svc.orders["O1"]["status"] == "HOLD"
    assert svc.reservations == []
