from datetime import date, datetime

import pytest

from src.services.warehouse import Warehouse, Zone, Bin
from src.services.inventory import InventoryService
from src.services.expiry import ExpiryService


def setup_br09():
    wh = Warehouse()
    wh.zones["Z"] = Zone("Z", "Ambient", "AMBIENT", "1")

    wh.bins["B1"] = Bin(
        "B1", "Z", 1, 1, "RESERVE", "AMBIENT", 100, 500
    )
    wh.bins["Q1"] = Bin(
        "Q1", "Z", 1, 2, "QUARANTINE", "AMBIENT", 100, 500
    )

    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "temp_class": "AMBIENT",
            "expiry_tracked": True
        }
    }

    inv = InventoryService(wh, sku)
    svc = ExpiryService(inv, wh)

    return inv, svc


def test_br09_leap_year_seven_day_boundary():
    assert ExpiryService.is_pickable(
        date(2024, 3, 7),
        date(2024, 2, 29)
    ) is False

    assert ExpiryService.is_pickable(
        date(2024, 3, 8),
        date(2024, 2, 29)
    ) is True


def test_br09_moves_blocked_stock_to_quarantine_bin():
    inv, svc = setup_br09()

    inv.add_stock(
        "B1", "SKU1", "LOT1", 10,
        date(2028, 1, 1),
        expiry_date=date(2028, 1, 17)
    )

    result = svc.quarantine_due(
        datetime(2028, 1, 10, 23, 59, 59),
        {"AMBIENT": "Q1"}
    )

    assert result == [("SKU1", "LOT1")]
    assert ("B1", "SKU1", "LOT1") not in inv.stock
    assert inv.stock[("Q1", "SKU1", "LOT1")].qty == 10
    assert inv.stock[("Q1", "SKU1", "LOT1")].status == "QUARANTINE"


def test_br09_quarantine_not_allowed_before_end_of_day():
    inv, svc = setup_br09()

    inv.add_stock(
        "B1", "SKU1", "LOT1", 10,
        date(2028, 1, 1),
        expiry_date=date(2028, 1, 17)
    )

    with pytest.raises(ValueError, match="end of day"):
        svc.quarantine_due(datetime(2028, 1, 10, 12, 0))

    assert inv.stock[("B1", "SKU1", "LOT1")].status == "AVAILABLE"
