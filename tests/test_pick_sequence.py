from src.services.pick_sequence import PickSequenceService
from src.services.warehouse import Bin, Warehouse, Zone


def make_service():
    warehouse = Warehouse()
    warehouse.zones["ZONE-1"] = Zone("ZONE-1", "Ambient", "AMBIENT", "1,2")
    for aisle, bin_no in [(1, 2), (1, 4), (2, 1), (2, 3)]:
        bin_id = f"BIN-{aisle}-{bin_no}"
        warehouse.bins[bin_id] = Bin(
            bin_id, "ZONE-1", aisle, bin_no, "PICK_FACE",
            "AMBIENT", 100, 100
        )
    return PickSequenceService(warehouse)


def test_pick_list_uses_ascending_aisles_and_serpentine_bin_order():
    service = make_service()
    pick_list = [
        {"bin_id": "BIN-2-1", "lot_no": "LOT-C"},
        {"bin_id": "BIN-1-4", "lot_no": "LOT-B"},
        {"bin_id": "BIN-2-3", "lot_no": "LOT-D"},
        {"bin_id": "BIN-1-2", "lot_no": "LOT-A"},
    ]

    result = service.sequence_pick_list(pick_list)

    assert [(item["bin_id"], item["walk_direction"]) for item in result] == [
        ("BIN-1-2", "UP"),
        ("BIN-1-4", "UP"),
        ("BIN-2-3", "DOWN"),
        ("BIN-2-1", "DOWN"),
    ]
    assert pick_list[0]["bin_id"] == "BIN-2-1"
    assert "walk_direction" not in pick_list[0]


def test_empty_pick_list_has_no_sequence():
    assert make_service().sequence_pick_list([]) == []
