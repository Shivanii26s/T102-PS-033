from datetime import date, datetime

from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def setup_inventory():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1.0,
            "expiry_tracked": True,
            "temp_class": "AMBIENT"
        }
    }

    inv = InventoryService(sku_master=sku)

    inv.add_stock(
        "B1", "SKU1", "LOT-LATE",
        5, date(2028, 1, 2),
        expiry_date=date(2028, 5, 1)
    )

    # Earlier expiry, but still at least 60 days remaining.
    inv.add_stock(
        "B2", "SKU1", "LOT-EARLY",
        8, date(2028, 1, 3),
        expiry_date=date(2028, 4, 15)
    )

    return inv, sku


def test_on_hand_and_remove():
    inv, _ = setup_inventory()

    assert inv.on_hand("SKU1") == 13

    inv.remove_stock("B1", "SKU1", "LOT-LATE", 2)

    assert inv.on_hand("SKU1") == 11


def test_fefo_reservation():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)

    result = svc.reserve_order(
        "O1",
        {"SKU1": 4},
        datetime(2028, 1, 10),
        False
    )

    assert result[0].lot_no == "LOT-EARLY"
    assert result[0].qty == 4


def test_all_or_nothing_hold():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)

    result = svc.reserve_order(
        "O1",
        {"SKU1": 99},
        datetime(2028, 1, 10),
        False
    )

    assert result == []
    assert svc.orders["O1"]["status"] == "HOLD"


def test_reservation_expiry():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)

    svc.reserve_order(
        "O1",
        {"SKU1": 2},
        datetime(2028, 1, 10),
        False
    )

    released = svc.release_expired(
        datetime(2028, 1, 12, 1)
    )

    assert len(released) == 1


from types import SimpleNamespace


class FakeWarehouse:
    def __init__(self, capacity_units=20, max_weight_kg=500):
        self.bin = SimpleNamespace(
            bin_id="B1",
            temp_class="AMBIENT",
            bin_type="RESERVE",
            capacity_units=capacity_units,
            max_weight_kg=max_weight_kg,
        )

    def get_bin(self, bin_id):
        if bin_id != "B1":
            raise ValueError("Unknown bin")
        return self.bin


def test_br02_exact_unit_and_weight_capacity_allowed():
    sku = {
        "SKU1": {
            "unit_weight_kg": 50,
            "temp_class": "AMBIENT"
        }
    }

    warehouse = FakeWarehouse(
        capacity_units=10,
        max_weight_kg=500
    )

    inv = InventoryService(warehouse, sku)
    inv.add_stock("B1", "SKU1", "LOT1", 10)

    assert inv.qty_in_bin("B1") == 10
    assert inv.weight_in_bin("B1") == 500


def test_br02_unit_capacity_exceeded():
    import pytest

    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "temp_class": "AMBIENT"
        }
    }

    warehouse = FakeWarehouse(
        capacity_units=10,
        max_weight_kg=500
    )

    inv = InventoryService(warehouse, sku)

    with pytest.raises(ValueError, match="Unit capacity exceeded"):
        inv.add_stock("B1", "SKU1", "LOT1", 11)


def test_br02_weight_capacity_exceeded():
    import pytest

    sku = {
        "SKU1": {
            "unit_weight_kg": 50.1,
            "temp_class": "AMBIENT"
        }
    }

    warehouse = FakeWarehouse(
        capacity_units=20,
        max_weight_kg=500
    )

    inv = InventoryService(warehouse, sku)

    with pytest.raises(ValueError, match="Weight capacity exceeded"):
        inv.add_stock("B1", "SKU1", "LOT1", 10)


def test_br02_maximum_two_distinct_skus():
    import pytest

    sku = {
        "SKU1": {"unit_weight_kg": 1, "temp_class": "AMBIENT"},
        "SKU2": {"unit_weight_kg": 1, "temp_class": "AMBIENT"},
        "SKU3": {"unit_weight_kg": 1, "temp_class": "AMBIENT"},
    }

    warehouse = FakeWarehouse()
    inv = InventoryService(warehouse, sku)

    inv.add_stock("B1", "SKU1", "LOT1", 1)
    inv.add_stock("B1", "SKU2", "LOT2", 1)

    with pytest.raises(ValueError, match="Maximum two SKUs"):
        inv.add_stock("B1", "SKU3", "LOT3", 1)


def test_br03_non_expiry_stock_over_90_days_becomes_slow():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)
    inv.add_stock("B1", "SKU1", "OLD", 5, date(2028, 1, 1))

    inv.refresh_slow_stock(date(2028, 4, 1))

    assert inv.stock[("B1", "SKU1", "OLD")].status == "SLOW"


def test_br03_exactly_90_days_is_not_slow():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": False
        }
    }

    inv = InventoryService(sku_master=sku)
    inv.add_stock("B1", "SKU1", "LOT90", 5, date(2028, 1, 2))

    inv.refresh_slow_stock(date(2028, 4, 1))

    assert inv.stock[("B1", "SKU1", "LOT90")].status == "AVAILABLE"


def test_br03_expiry_tracked_stock_is_not_slow():
    sku = {
        "SKU1": {
            "unit_weight_kg": 1,
            "expiry_tracked": True
        }
    }

    inv = InventoryService(sku_master=sku)
    inv.add_stock("B1", "SKU1", "EXPIRY", 5, date(2028, 1, 1))

    inv.refresh_slow_stock(date(2028, 4, 1))

    assert inv.stock[("B1", "SKU1", "EXPIRY")].status == "AVAILABLE"