from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class StockKey:
    bin_id: str
    sku_id: str
    lot_no: str


@dataclass
class StockLot:
    bin_id: str
    sku_id: str
    lot_no: str
    qty: int
    grn_date: date
    mfg_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: str = "AVAILABLE"  # AVAILABLE, QUARANTINE, BLOCKED


@dataclass
class Movement:
    timestamp: datetime
    movement_type: str
    sku_id: str
    lot_no: str
    qty: int
    from_bin: Optional[str] = None
    to_bin: Optional[str] = None
    reference: str = ""
    note: str = ""


@dataclass
class Reservation:
    order_id: str
    sku_id: str
    lot_no: str
    bin_id: str
    qty: int
    created_at: datetime
    expires_at: datetime
    confirmed: bool = False
    released: bool = False


@dataclass
class Order:
    order_id: str
    created_at: datetime
    allow_short: bool
    lines: dict[str, int]
    status: str = "NEW"
    reservations: list[Reservation] = field(default_factory=list)
