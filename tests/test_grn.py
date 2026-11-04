
from pathlib import Path
import pytest

from src.services.grn import GRNService


def test_load_grn_data():
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"

    service = GRNService()
    service.load_skus(data_dir / "skus.csv")
    service.load_grn_lines(data_dir / "grn_lines.csv")

    assert len(service.skus) > 0
    assert len(service.grn_lines) > 0
    assert len(service.get_grn_ids()) > 0


def test_get_grn_lines():
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"

    service = GRNService()
    service.load_skus(data_dir / "skus.csv")
    service.load_grn_lines(data_dir / "grn_lines.csv")

    grn_id = service.get_grn_ids()[0]
    lines = service.receive_grn(grn_id)

    assert len(lines) > 0
    assert all(line.grn_id == grn_id for line in lines)
    assert lines == sorted(lines, key=lambda line: line.line_no)


def test_unknown_grn():
    service = GRNService()

    with pytest.raises(ValueError, match="GRN not found"):
        service.receive_grn("GRN-UNKNOWN")
