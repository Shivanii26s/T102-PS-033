import csv
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class GRNLine:
    grn_id: str
    line_no: int
    grn_ts: datetime
    supplier_id: str
    sku_id: str
    lot_no: str
    qty: int
    mfg_date: date | None
    expiry_date: date | None


class GRNService:
    """Validates GRN source rows. Invalid rows are retained in rejected_rows, not fatal to the batch."""
    def __init__(self):
        self.skus = {}
        self.grn_lines = {}
        self.rejected_rows = []

    def load_skus(self, file_path):
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sku_id = row["sku_id"].strip()
                if not sku_id or sku_id in self.skus:
                    raise ValueError(f"Missing or duplicate SKU: {sku_id}")
                weight = float(row["unit_weight_kg"])
                if weight <= 0:
                    raise ValueError(f"Invalid unit weight for {sku_id}")
                self.skus[sku_id] = {
                    "description": row["description"].strip(),
                    "unit_weight_kg": weight,
                    "temp_class": row["temp_class"].strip().upper(),
                    "expiry_tracked": row["expiry_tracked"].strip().lower() == "true",
                    "home_zone": row["home_zone"].strip(),
                    "pick_face_bin": row["pick_face_bin"].strip(),
                }

    @staticmethod
    def _date(value, field):
        value = (value or "").strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid {field}: {value}") from None

    def _parse_row(self, row):
        grn_id, sku_id, lot_no = row["grn_id"].strip(), row["sku_id"].strip(), row["lot_no"].strip()
        if not grn_id or not sku_id or not lot_no:
            raise ValueError("GRN ID, SKU ID and lot number are required")
        if self.skus and sku_id not in self.skus:
            raise ValueError(f"Unknown SKU: {sku_id}")
        line_no, qty = int(row["line_no"]), int(row["qty"])
        if line_no <= 0 or qty <= 0:
            raise ValueError("Line number and quantity must be positive")
        mfg = self._date(row.get("mfg_date"), "manufacturing date")
        expiry = self._date(row.get("expiry_date"), "expiry date")
        if mfg and expiry and expiry < mfg:
            raise ValueError("Expiry date is before manufacturing date")
        if sku_id in self.skus and self.skus[sku_id]["expiry_tracked"] and not expiry:
            raise ValueError(f"Expiry date required for expiry-tracked SKU {sku_id}")
        return GRNLine(grn_id, line_no, datetime.fromisoformat(row["grn_ts"].strip()),
                       row["supplier_id"].strip(), sku_id, lot_no, qty, mfg, expiry)

    def load_grn_lines(self, file_path, strict=False):
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            for row_number, row in enumerate(csv.DictReader(f), start=2):
                try:
                    line = self._parse_row(row)
                    key = (line.grn_id, line.line_no)
                    if key in self.grn_lines:
                        raise ValueError(f"Duplicate GRN line: {key}")
                    self.grn_lines[key] = line
                except (ValueError, KeyError) as exc:
                    issue = {"row": row_number, "data": row, "reason": str(exc)}
                    self.rejected_rows.append(issue)
                    if strict:
                        raise ValueError(f"GRN CSV row {row_number}: {exc}") from exc
        return self.grn_lines

    def get_grn_lines(self, grn_id):
        lines = [v for (gid, _), v in self.grn_lines.items() if gid == grn_id]
        if not lines:
            raise ValueError(f"GRN not found or contains no valid lines: {grn_id}")
        return sorted(lines, key=lambda x: x.line_no)

    def get_grn_ids(self):
        return sorted({gid for gid, _ in self.grn_lines})

    def receive_grn(self, grn_id):
        return self.get_grn_lines(grn_id)
