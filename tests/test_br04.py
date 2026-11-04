
from datetime import date, datetime

from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def test_br04_fefo_selects_earliest_expiry():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": True
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock(
        "B1", "SKU1", "LATER",
        10, date(2028, 1, 1),
        expiry_date=date(2028, 6, 1)
    )

    inv.add_stock(
        "B2", "SKU1", "EARLIER",
        10, date(2028, 1, 2),
        expiry_date=date(2028, 4, 1)
    )

    service = ReservationService(inv, sku)

    result = service.reserve_order(
        "O1", {"SKU1": 5},
        datetime(2028, 2, 1)
    )

    assert result[0].lot_no == "EARLIER"
    assert result[0].bin_id == "B2"


def test_br04_fifo_selects_oldest_grn_date():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock(
        "B2", "SKU1", "NEW",
        10, date(2028, 1, 10)
    )

    inv.add_stock(
        "B1", "SKU1", "OLD",
        10, date(2028, 1, 1)
    )

    service = ReservationService(inv, sku)

    result = service.reserve_order(
        "O1", {"SKU1": 5},
        datetime(2028, 2, 1)
    )

    assert result[0].lot_no == "OLD"


def test_br04_equal_expiry_uses_lowest_bin_id():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": True
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock(
        "B2", "SKU1", "LOT2",
        10, date(2028, 1, 1),
        expiry_date=date(2028, 5, 1)
    )

    inv.add_stock(
        "B1", "SKU1", "LOT1",
        10, date(2028, 1, 1),
        expiry_date=date(2028, 5, 1)
    )

    service = ReservationService(inv, sku)

    result = service.reserve_order(
        "O1", {"SKU1": 5},
        datetime(2028, 2, 1)
    )

    assert result[0].bin_id == "B1"


def test_br04_slow_stock_selected_after_normal_fifo_stock():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock(
        "B1", "SKU1", "OLD",
        10, date(2028, 1, 1)
    )

    inv.add_stock(
        "B2", "SKU1", "NORMAL",
        10, date(2028, 4, 5)
    )

    inv.refresh_slow_stock(date(2028, 4, 10))

    service = ReservationService(inv, sku)

    result = service.reserve_order(
        "O1", {"SKU1": 5},
        datetime(2028, 4, 10)
    )

    assert result[0].lot_no == "NORMAL"
