
import csv
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
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
    def __init__(self):
        self.skus = {}
        self.grn_lines = {}

    def load_skus(self, file_path):
        with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                sku_id = row["sku_id"].strip()

                if not sku_id:
                    raise ValueError("SKU ID cannot be empty")

                if sku_id in self.skus:
                    raise ValueError(f"Duplicate SKU: {sku_id}")

                self.skus[sku_id] = {
                    "expiry_tracked": row["expiry_tracked"].strip().lower()
                    == "true",
                    "unit_weight_kg": float(row["unit_weight_kg"]),
                    "temp_class": row["temp_class"].strip()
                }

    @staticmethod
    def _parse_date(value, field_name):
        value = value.strip()

        if not value:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid {field_name}: {value}")

    @staticmethod
    def _parse_datetime(value):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            raise ValueError(f"Invalid GRN timestamp: {value}")

    def load_grn_lines(self, file_path):
        with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                grn_id = row["grn_id"].strip()
                sku_id = row["sku_id"].strip()
                lot_no = row["lot_no"].strip()

                if not grn_id or not sku_id or not lot_no:
                    raise ValueError("GRN ID, SKU ID and lot number are required")

                if self.skus and sku_id not in self.skus:
                    raise ValueError(f"Unknown SKU: {sku_id}")

                line_no = int(row["line_no"])
                qty = int(row["qty"])

                if line_no <= 0:
                    raise ValueError("GRN line number must be positive")

                if qty <= 0:
                    raise ValueError(
                        f"GRN quantity must be positive: {grn_id}"
                    )

                mfg_date = self._parse_date(row["mfg_date"], "manufacturing date")
                expiry_date = self._parse_date(row["expiry_date"], "expiry date")

                if mfg_date and expiry_date and expiry_date < mfg_date:
                    raise ValueError(
                        f"Expiry date is before manufacturing date: {grn_id}"
                    )

                if self.skus:
                    sku = self.skus[sku_id]
                    if sku["expiry_tracked"] and expiry_date is None:
                        raise ValueError(
                            f"Expiry date required for SKU {sku_id}"
                        )

                key = (grn_id, line_no)

                if key in self.grn_lines:
                    raise ValueError(
                        f"Duplicate GRN line: {grn_id}, line {line_no}"
                    )

                line = GRNLine(
                    grn_id=grn_id,
                    line_no=line_no,
                    grn_ts=self._parse_datetime(row["grn_ts"]),
                    supplier_id=row["supplier_id"].strip(),
                    sku_id=sku_id,
                    lot_no=lot_no,
                    qty=qty,
                    mfg_date=mfg_date,
                    expiry_date=expiry_date
                )

                self.grn_lines[key] = line

    def get_grn_lines(self, grn_id):
        lines = [
            line for (current_grn, _), line in self.grn_lines.items()
            if current_grn == grn_id
        ]

        if not lines:
            raise ValueError(f"GRN not found: {grn_id}")

        return sorted(lines, key=lambda line: line.line_no)

    def get_grn_ids(self):
        return sorted({grn_id for grn_id, _ in self.grn_lines})

    def receive_grn(self, grn_id):
        """Return all validated lines for a GRN receiving command."""
        return self.get_grn_lines(grn_id)
