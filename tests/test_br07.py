from datetime import date, datetime

from src.services.warehouse import Warehouse, Zone, Bin
from src.services.inventory import InventoryService
from src.services.replenishment import ReplenishmentService


def setup_br07(expiry_tracked=False):
    wh = Warehouse()
    wh.zones["Z"] = Zone("Z", "Ambient", "AMBIENT", "1")

    wh.bins["P"] = Bin(
        "P", "Z", 1, 1, "PICK_FACE", "AMBIENT", 100, 500
    )
    wh.bins["R1"] = Bin(
        "R1", "Z", 1, 2, "RESERVE", "AMBIENT", 200, 500
    )
    wh.bins["R2"] = Bin(
        "R2", "Z", 1, 3, "RESERVE", "AMBIENT", 200, 500
    )
    wh.bins["Q"] = Bin(
        "Q", "Z", 1, 4, "QUARANTINE", "AMBIENT", 200, 500
    )

    sku = {
        "S": {
            "unit_weight_kg": 1,
            "temp_class": "AMBIENT",
            "pick_face_bin": "P",
            "expiry_tracked": expiry_tracked
        }
    }

    inv = InventoryService(wh, sku)
    svc = ReplenishmentService(inv, wh, sku)

    return wh, inv, svc


def test_br07_exactly_20_percent_does_not_replenish():
    _, inv, svc = setup_br07()

    inv.add_stock("P", "S", "PICK", 20, date(2028, 1, 1))
    inv.add_stock("R1", "S", "RESERVE", 100, date(2028, 1, 1))

    result = svc.replenish("S", datetime(2028, 2, 1))

    assert result["status"] == "NOT_REQUIRED"
    assert result["moved_qty"] == 0
    assert inv.on_hand("S", "P") == 20


def test_br07_below_20_percent_refills_to_80_percent():
    _, inv, svc = setup_br07()

    inv.add_stock("P", "S", "PICK", 19, date(2028, 1, 1))
    inv.add_stock("R1", "S", "RESERVE", 100, date(2028, 1, 1))

    result = svc.replenish("S", datetime(2028, 2, 1))

    assert result["status"] == "REPLENISHED"
    assert result["moved_qty"] == 61
    assert result["pick_face_qty"] == 80
    assert result["target_qty"] == 80


def test_br07_fifo_selects_oldest_non_expiry_lot():
    _, inv, svc = setup_br07()

    inv.add_stock("P", "S", "PICK", 10, date(2028, 1, 1))
    inv.add_stock("R2", "S", "NEW", 40, date(2028, 1, 5))
    inv.add_stock("R1", "S", "OLD", 40, date(2028, 1, 2))

    svc.replenish("S", datetime(2028, 2, 1))

    assert inv.stock[("P", "S", "OLD")].qty == 40
    assert inv.stock[("P", "S", "NEW")].qty == 30


def test_br07_fefo_selects_earliest_expiry_lot():
    _, inv, svc = setup_br07(expiry_tracked=True)

    inv.add_stock("P", "S", "PICK", 10, date(2028, 1, 1))

    inv.add_stock(
        "R1", "S", "LATE", 40,
        date(2028, 1, 1), expiry_date=date(2028, 8, 1)
    )
    inv.add_stock(
        "R2", "S", "EARLY", 40,
        date(2028, 1, 2), expiry_date=date(2028, 5, 1)
    )

    svc.replenish("S", datetime(2028, 2, 1))

    assert inv.stock[("P", "S", "EARLY")].qty == 40
    assert inv.stock[("P", "S", "LATE")].qty == 30


def test_br07_quarantine_stock_is_never_replenished():
    _, inv, svc = setup_br07()

    inv.add_stock("P", "S", "PICK", 10, date(2028, 1, 1))
    inv.add_stock(
        "Q", "S", "QUARANTINED", 100,
        date(2028, 1, 1), status="QUARANTINE"
    )

    result = svc.replenish("S", datetime(2028, 2, 1))

    assert result["moved_qty"] == 0
    assert result["status"] == "NO_RESERVE_STOCK"
    assert inv.stock[("Q", "S", "QUARANTINED")].qty == 100
