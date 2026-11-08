from datetime import date

from src.services.inventory import InventoryService
from src.services.shelf_life import ShelfLifeService


def make_service(expiry_tracked=False):
    sku_master = {
        "SKU-1": {
            "expiry_tracked": expiry_tracked,
            "unit_weight_kg": 1.0,
        }
    }
    inventory = InventoryService(sku_master=sku_master)
    return inventory, ShelfLifeService(inventory)


def test_minimum_shelf_life_accepts_exactly_60_days():
    inventory, service = make_service(expiry_tracked=True)
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-60", 1,
        date(2028, 1, 1), expiry_date=date(2028, 3, 20)
    )
    inventory.add_stock(
        "BIN-2", "SKU-1", "LOT-59", 1,
        date(2028, 1, 1), expiry_date=date(2028, 3, 19)
    )

    lots = service.get_pickable_lots("SKU-1", date(2028, 1, 20))

    assert [lot.lot_no for lot in lots] == ["LOT-60"]


def test_expiry_tracked_lot_without_expiry_is_not_pickable():
    inventory, service = make_service(expiry_tracked=True)
    inventory.add_stock("BIN-1", "SKU-1", "LOT-NO-EXPIRY", 1)

    assert service.get_pickable_lots("SKU-1", date(2028, 1, 20)) == []


def test_slow_moving_starts_after_90_days_and_is_sorted_last():
    inventory, service = make_service()
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-90", 1, date(2027, 10, 22)
    )
    inventory.add_stock(
        "BIN-2", "SKU-1", "LOT-91", 1, date(2027, 10, 21)
    )
    as_of = date(2028, 1, 20)

    lots = service.get_pickable_lots("SKU-1", as_of)

    assert service.is_slow_moving(lots[0], as_of) is False
    assert [lot.lot_no for lot in lots] == ["LOT-90", "LOT-91"]
    assert service.is_slow_moving(lots[1], as_of) is True
