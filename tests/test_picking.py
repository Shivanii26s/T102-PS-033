
from datetime import date

import pytest

from src.services.inventory import InventoryService
from src.services.picking import PickingService


def make_service(expiry_tracked=False):
    sku_master = {
        "SKU-001": {
            "description": "Rice",
            "unit_weight_kg": 1.0,
            "temp_class": "AMBIENT",
            "expiry_tracked": expiry_tracked,
            "home_zone": "ZN-A",
            "pick_face_bin": "BIN-1",
        }
    }

    inventory = InventoryService(sku_master=sku_master)
    service = PickingService(inventory, sku_master)

    return inventory, service


def test_fifo_picks_oldest_recent_grn_first():
    inventory, service = make_service()

    inventory.add_stock(
        "BIN-2", "SKU-001", "LOT-NEW", 10,
        grn_date=date(2028, 1, 15)
    )
    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-OLD", 10,
        grn_date=date(2028, 1, 10)
    )

    lots = service.get_pickable_lots("SKU-001", date(2028, 1, 20))

    assert [lot.lot_no for lot in lots] == ["LOT-OLD", "LOT-NEW"]


def test_fefo_picks_earliest_expiry_first():
    inventory, service = make_service(expiry_tracked=True)

    inventory.add_stock(
        "BIN-2", "SKU-001", "LOT-LATE", 10,
        grn_date=date(2028, 1, 1),
        expiry_date=date(2028, 6, 30)
    )
    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-EARLY", 10,
        grn_date=date(2028, 1, 5),
        expiry_date=date(2028, 5, 30)
    )

    lots = service.get_pickable_lots("SKU-001", date(2028, 1, 20))

    assert [lot.lot_no for lot in lots] == ["LOT-EARLY", "LOT-LATE"]


def test_fefo_uses_lowest_bin_id_when_expiry_dates_tie():
    inventory, service = make_service(expiry_tracked=True)

    inventory.add_stock(
        "BIN-2", "SKU-001", "LOT-B", 10,
        grn_date=date(2028, 1, 1),
        expiry_date=date(2028, 6, 30)
    )
    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-A", 10,
        grn_date=date(2028, 1, 1),
        expiry_date=date(2028, 6, 30)
    )

    lots = service.get_pickable_lots("SKU-001", date(2028, 1, 20))

    assert [lot.bin_id for lot in lots] == ["BIN-1", "BIN-2"]


def test_fefo_excludes_lots_with_less_than_60_days_shelf_life():
    inventory, service = make_service(expiry_tracked=True)

    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-59", 10,
        grn_date=date(2028, 1, 1),
        expiry_date=date(2028, 3, 19)
    )
    inventory.add_stock(
        "BIN-2", "SKU-001", "LOT-60", 10,
        grn_date=date(2028, 1, 1),
        expiry_date=date(2028, 3, 20)
    )

    lots = service.get_pickable_lots("SKU-001", date(2028, 1, 20))

    assert [lot.lot_no for lot in lots] == ["LOT-60"]


def test_pick_list_does_not_deduct_stock_until_confirmed():
    inventory, service = make_service()

    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-1", 20,
        grn_date=date(2028, 1, 10)
    )

    allocations = service.create_pick_list(
        "SKU-001", 5, date(2028, 1, 20)
    )

    assert allocations[0]["qty"] == 5
    assert inventory.on_hand("SKU-001") == 20

    service.confirm_pick(allocations)

    assert inventory.on_hand("SKU-001") == 15


def test_pick_list_rejects_insufficient_stock():
    inventory, service = make_service()

    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-1", 5,
        grn_date=date(2028, 1, 10)
    )

    with pytest.raises(ValueError, match="Insufficient pickable stock"):
        service.create_pick_list("SKU-001", 10, date(2028, 1, 20))
