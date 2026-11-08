import pytest
from datetime import date

from src.services.inventory import InventoryService


def make_inventory():
    inv = InventoryService()
    inv.add_stock("B1", "SKU1", "LOT1", 20, date(2028, 1, 1))
    return inv


def test_frozen_bin_rejects_new_stock():
    inv = make_inventory()
    inv.frozen_bins.add("B1")

    with pytest.raises(ValueError, match="frozen"):
        inv.add_stock("B1", "SKU1", "LOT2", 5)


def test_frozen_bin_rejects_picking():
    inv = make_inventory()
    inv.frozen_bins.add("B1")

    with pytest.raises(ValueError, match="frozen"):
        inv.remove_stock("B1", "SKU1", "LOT1", 5)


def test_frozen_bin_rejects_transfer_out():
    inv = make_inventory()
    inv.frozen_bins.add("B1")

    with pytest.raises(ValueError, match="frozen"):
        inv.move_stock("B1", "B2", "SKU1", "LOT1", 5)


def test_frozen_bin_rejects_transfer_in():
    inv = make_inventory()
    inv.add_stock("B2", "SKU1", "LOT2", 10)
    inv.frozen_bins.add("B1")

    with pytest.raises(ValueError, match="frozen"):
        inv.move_stock("B2", "B1", "SKU1", "LOT2", 5)


def test_frozen_bin_allows_cycle_count_adjustment():
    inv = make_inventory()
    inv.frozen_bins.add("B1")

    inv.remove_stock(
        "B1",
        "SKU1",
        "LOT1",
        2,
        reference="CYCLE_COUNT_ADJUSTMENT",
        movement_type="ADJUSTMENT"
    )

    assert inv.on_hand("SKU1", "B1") == 18


def test_frozen_bin_allows_expiry_quarantine_transfer_out():
    inv = make_inventory()
    inv.frozen_bins.add("B1")

    inv.move_stock(
        "B1",
        "Q1",
        "SKU1",
        "LOT1",
        5,
        reference="EXPIRY_QUARANTINE",
        status="QUARANTINE"
    )

    assert inv.on_hand("SKU1", "B1") == 15
    assert inv.on_hand("SKU1", "Q1", include_quarantine=True) == 5