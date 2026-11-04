from datetime import date, datetime
from src.services.inventory import InventoryService
from src.services.reservation import ReservationService


def setup_inventory():
    sku = {"SKU1": {"unit_weight_kg": 1.0, "expiry_tracked": True, "temp_class": "AMBIENT"}}
    inv = InventoryService(sku_master=sku)
    inv.add_stock("B1", "SKU1", "LOT-LATE", 5, date(2028, 1, 2), expiry_date=date(2028, 5, 1))
    inv.add_stock("B2", "SKU1", "LOT-EARLY", 8, date(2028, 1, 3), expiry_date=date(2028, 3, 1))
    return inv, sku


def test_on_hand_and_remove():
    inv, _ = setup_inventory()
    assert inv.on_hand("SKU1") == 13
    inv.remove_stock("B1", "SKU1", "LOT-LATE", 2)
    assert inv.on_hand("SKU1") == 11


def test_fefo_reservation():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)
    result = svc.reserve_order("O1", {"SKU1": 4}, datetime(2028, 1, 10), False)
    assert result[0].lot_no == "LOT-EARLY"
    assert result[0].qty == 4


def test_all_or_nothing_hold():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)
    result = svc.reserve_order("O1", {"SKU1": 99}, datetime(2028, 1, 10), False)
    assert result == []
    assert svc.orders["O1"]["status"] == "HOLD"


def test_reservation_expiry():
    inv, sku = setup_inventory()
    svc = ReservationService(inv, sku)
    svc.reserve_order("O1", {"SKU1": 2}, datetime(2028, 1, 10), False)
    released = svc.release_expired(datetime(2028, 1, 12, 1))
    assert len(released) == 1
