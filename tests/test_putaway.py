
from datetime import date, datetime

from src.services.warehouse import Warehouse, Bin, Zone
from src.services.inventory import InventoryService
from src.services.grn import GRNLine
from src.services.putaway import PutawayService


def test_putaway_prefers_existing_same_sku_lot():
    warehouse = Warehouse()

    warehouse.zones["ZN-A"] = Zone(
        "ZN-A", "Ambient", "AMBIENT", "1,2"
    )

    warehouse.bins["BIN-1"] = Bin(
        "BIN-1", "ZN-A", 1, 1, "RESERVE",
        "AMBIENT", 100, 100
    )
    warehouse.bins["BIN-2"] = Bin(
        "BIN-2", "ZN-A", 2, 1, "RESERVE",
        "AMBIENT", 100, 100
    )

    sku_master = {
        "SKU-001": {
            "description": "Rice",
            "unit_weight_kg": 1.0,
            "temp_class": "AMBIENT",
            "expiry_tracked": False,
            "home_zone": "ZN-A",
            "pick_face_bin": "BIN-1",
        }
    }

    inventory = InventoryService(warehouse, sku_master)

    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-1", 10,
        grn_date=date(2028, 1, 1)
    )

    service = PutawayService(warehouse, inventory, sku_master)

    grn_line = GRNLine(
        "GRN-001", 1, datetime(2028, 1, 19, 10, 0),
        "SUP-001", "SKU-001", "LOT-1", 20,
        None, None
    )

    result = service.putaway_line(grn_line)

    assert len(result) == 1
    assert result[0]["bin_id"] == "BIN-1"
    assert result[0]["qty"] == 20
    assert inventory.on_hand("SKU-001", "BIN-1", "LOT-1") == 30
    assert inventory.on_hand("SKU-001", "BIN-2", "LOT-1") == 0


def test_putaway_does_not_split_if_remainder_is_less_than_10():
    warehouse = Warehouse()

    warehouse.zones["ZN-A"] = Zone(
        "ZN-A", "Ambient", "AMBIENT", "1,2"
    )

    warehouse.bins["BIN-1"] = Bin(
        "BIN-1", "ZN-A", 1, 1, "RESERVE",
        "AMBIENT", 100, 100
    )

    warehouse.bins["BIN-2"] = Bin(
        "BIN-2", "ZN-A", 2, 1, "RESERVE",
        "AMBIENT", 100, 100
    )

    sku_master = {
        "SKU-001": {
            "description": "Rice",
            "unit_weight_kg": 1.0,
            "temp_class": "AMBIENT",
            "expiry_tracked": False,
            "home_zone": "ZN-A",
            "pick_face_bin": "BIN-1",
        }
    }

    inventory = InventoryService(warehouse, sku_master)

    inventory.add_stock(
        "BIN-1", "SKU-001", "LOT-1", 60,
        grn_date=date(2028, 1, 1)
    )

    service = PutawayService(warehouse, inventory, sku_master)

    grn_line = GRNLine(
        "GRN-002", 1, datetime(2028, 1, 19, 10, 0),
        "SUP-001", "SKU-001", "LOT-1", 45,
        None, None
    )

    result = service.putaway_line(grn_line)

    assert len(result) == 1
    assert result[0]["bin_id"] == "BIN-2"
    assert result[0]["qty"] == 45
    assert inventory.on_hand("SKU-001", "BIN-1", "LOT-1") == 60
    assert inventory.on_hand("SKU-001", "BIN-2", "LOT-1") == 45
