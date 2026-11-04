from datetime import date, datetime
from src.services.inventory import InventoryService
from src.services.expiry import ExpiryService


def test_seven_days_or_less_is_not_pickable():
    inv = InventoryService()
    inv.add_stock("B1", "S1", "L1", 4, date(2028, 1, 1), expiry_date=date(2028, 1, 17))
    svc = ExpiryService(inv)
    assert svc.is_pickable(date(2028, 1, 18), date(2028, 1, 10)) is True
    assert svc.is_pickable(date(2028, 1, 17), date(2028, 1, 10)) is False


def test_eod_quarantine():
    inv = InventoryService()
    inv.add_stock("B1", "S1", "L1", 4, date(2028, 1, 1), expiry_date=date(2028, 1, 17))
    svc = ExpiryService(inv)
    assert svc.quarantine_due(datetime(2028, 1, 10, 23, 59, 59)) == [("S1", "L1")]
    assert inv.stock[("B1", "S1", "L1")].status == "QUARANTINE"
