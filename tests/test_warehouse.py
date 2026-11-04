
from pathlib import Path

from src.services.warehouse import Warehouse


def test_load_warehouse():
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"

    warehouse = Warehouse()

    warehouse.load_warehouse(
        data_dir / "zones.csv",
        data_dir / "bins.csv"
    )

    assert len(warehouse.zones) > 0
    assert len(warehouse.bins) > 0


def test_get_bin():
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"

    warehouse = Warehouse()

    warehouse.load_warehouse(
        data_dir / "zones.csv",
        data_dir / "bins.csv"
    )

    bin_details = warehouse.get_bin("BIN-01-01")

    assert bin_details.bin_id == "BIN-01-01"
    assert bin_details.zone_id == "ZN-A"
    assert bin_details.bin_type == "PICK_FACE"
