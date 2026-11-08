from datetime import date, datetime
from src.services.warehouse import Warehouse, Zone, Bin
from src.services.inventory import InventoryService
from src.services.replenishment import ReplenishmentService


def test_replenishment_moves_oldest_lot():
    wh = Warehouse()
    wh.zones["Z"] = Zone("Z", "Ambient", "AMBIENT", "1")
    wh.bins["P"] = Bin("P", "Z", 1, 1, "PICK_FACE", "AMBIENT", 100, 500)
    wh.bins["R"] = Bin("R", "Z", 1, 2, "RESERVE", "AMBIENT", 200, 500)
    sku = {"S": {"unit_weight_kg": 1, "temp_class": "AMBIENT", "pick_face_bin": "P"}}
    inv = InventoryService(wh, sku)
    inv.add_stock("P", "S", "PICK", 10, date(2028, 1, 1))
    inv.add_stock("R", "S", "OLD", 60, date(2028, 1, 1))
    inv.add_stock("R", "S", "NEW", 60, date(2028, 1, 2))
    svc = ReplenishmentService(inv, wh, sku)
    result = svc.replenish("S", datetime(2028, 1, 5))
    assert result["moved_qty"] == 70
    assert inv.stock[("P", "S", "OLD")].qty == 60
    assert inv.stock[("P", "S", "NEW")].qty == 10


def test_replenishment_respects_pick_face_weight_limit():
    wh = Warehouse()
    wh.zones["Z"] = Zone("Z", "Ambient", "AMBIENT", "1")
    wh.bins["P"] = Bin(
        "P", "Z", 1, 1, "PICK_FACE", "AMBIENT", 100, 500
    )
    wh.bins["R"] = Bin(
        "R", "Z", 1, 2, "RESERVE", "AMBIENT", 200, 3000
    )
    sku = {
        "S": {
            "unit_weight_kg": 25,
            "temp_class": "AMBIENT",
            "pick_face_bin": "P",
        }
    }
    inv = InventoryService(wh, sku)
    inv.add_stock("P", "S", "PICK", 12, date(2028, 1, 1))
    inv.add_stock("R", "S", "RESERVE", 100, date(2028, 1, 1))

    result = ReplenishmentService(inv, wh, sku).replenish(
        "S", datetime(2028, 1, 5)
    )

    assert result["moved_qty"] == 8
    assert result["pick_face_qty"] == 20
    assert result["short_qty"] == 60
    assert inv.weight_in_bin("P") == 500
