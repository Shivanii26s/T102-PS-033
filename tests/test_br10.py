from datetime import date

from src.services.inventory import InventoryService
from src.services.audit import AuditService


def test_br10_variance_above_threshold_freezes_bin():
    inv = InventoryService()
    audit = AuditService(inv)

    inv.add_stock("B1", "SKU1", "LOT1", 100, date(2028, 1, 1))

    result = audit.apply_adjustment(
        inv, "B1", "SKU1", "LOT1", 97
    )

    assert result["freeze_required"] is True
    assert "B1" in inv.frozen_bins


def test_br10_exactly_two_percent_does_not_freeze():
    inv = InventoryService()
    audit = AuditService(inv)

    inv.add_stock("B1", "SKU1", "LOT1", 100, date(2028, 1, 1))

    result = audit.apply_adjustment(
        inv, "B1", "SKU1", "LOT1", 98
    )

    assert result["freeze_required"] is False
    assert "B1" not in inv.frozen_bins


def test_br10_shortfall_reduces_oldest_lot_first():
    inv = InventoryService()
    audit = AuditService(inv)

    inv.add_stock("B1", "SKU1", "OLD", 10, date(2028, 1, 1))
    inv.add_stock("B1", "SKU1", "NEW", 20, date(2028, 1, 5))

    result = audit.apply_adjustment(
        inv, "B1", "SKU1", "OLD", 22
    )

    assert result["variance"] == -8

    assert inv.stock[("B1", "SKU1", "OLD")].qty == 2
    assert inv.stock[("B1", "SKU1", "NEW")].qty == 20

    assert inv.on_hand("SKU1", "B1") == 22
    assert "B1" in inv.frozen_bins