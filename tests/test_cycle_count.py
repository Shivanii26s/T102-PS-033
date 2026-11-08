from datetime import date, datetime

import pytest

from src.services.cycle_count import CycleCountService
from src.services.inventory import InventoryService


def test_variance_at_two_percent_boundary_does_not_freeze():
    inventory = InventoryService()
    service = CycleCountService(inventory)

    result = service.validate_count(100, 98)

    assert result["variance"] == -2
    assert result["freeze_required"] is False


def test_variance_at_five_unit_boundary_does_not_freeze():
    result = CycleCountService.validate_count(500, 495)

    assert result["freeze_required"] is False


def test_within_threshold_shortfall_is_adjusted_immediately():
    inventory = InventoryService()
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-1", 100, date(2028, 1, 1)
    )
    service = CycleCountService(inventory)

    result = service.apply_count("BIN-1", "SKU-1", 98)

    assert result["freeze_required"] is False
    assert inventory.on_hand("SKU-1", "BIN-1") == 98
    assert "BIN-1" not in inventory.frozen_bins


def test_variance_above_five_units_freezes_bin_and_defers_adjustment():
    inventory = InventoryService()
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-1", 100, date(2028, 1, 1)
    )
    service = CycleCountService(inventory)

    result = service.apply_count("BIN-1", "SKU-1", 94)

    assert result["freeze_required"] is True
    assert "BIN-1" in inventory.frozen_bins
    assert inventory.on_hand("SKU-1", "BIN-1") == 100


def test_shortfall_adjustment_removes_oldest_lot_first_and_unfreezes():
    inventory = InventoryService()
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-OLD", 60, date(2027, 1, 1)
    )
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-NEW", 60, date(2027, 2, 1)
    )
    service = CycleCountService(inventory)
    service.apply_count("BIN-1", "SKU-1", 114)

    service.adjust_bin("BIN-1", datetime(2028, 1, 1, 12))

    assert inventory.on_hand("SKU-1", "BIN-1") == 114
    assert inventory.stock[("BIN-1", "SKU-1", "LOT-OLD")].qty == 54
    assert inventory.stock[("BIN-1", "SKU-1", "LOT-NEW")].qty == 60
    assert "BIN-1" not in inventory.frozen_bins
    assert inventory.movements[-1].movement_type == "ADJUSTMENT"


def test_positive_adjustment_uses_the_supplied_lot():
    inventory = InventoryService()
    inventory.add_stock(
        "BIN-1", "SKU-1", "LOT-1", 10, date(2028, 1, 1)
    )
    service = CycleCountService(inventory)

    result = service.apply_count(
        "BIN-1", "SKU-1", 12, lot_no="LOT-1", timestamp=date(2028, 1, 2)
    )
    assert result["freeze_required"] is True
    service.adjust_bin("BIN-1")

    assert inventory.stock[("BIN-1", "SKU-1", "LOT-1")].qty == 12
    assert isinstance(inventory.movements[-1].timestamp, datetime)


def test_negative_count_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        CycleCountService.validate_count(10, -1)
