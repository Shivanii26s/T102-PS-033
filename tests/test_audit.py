from src.services.inventory import InventoryService
from src.services.audit import AuditService


def test_count_variance_threshold():
    result = AuditService.count_variance(100, 97)
    assert result["variance"] == -3
    assert result["freeze_required"] is True


def test_count_variance_within_threshold():
    result = AuditService.count_variance(100, 99)
    assert result["freeze_required"] is False


def test_snapshot_empty_inventory():
    audit = AuditService(InventoryService())
    assert audit.stock_snapshot() == []
