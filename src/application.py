import csv
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, time
from pathlib import Path

from src.services.audit import AuditService
from src.services.cycle_count import CycleCountService
from src.services.expiry import ExpiryService
from src.services.grn import GRNService
from src.services.inventory import InventoryService
from src.services.pick_sequence import PickSequenceService
from src.services.picking import PickingService
from src.services.putaway import PutawayService
from src.services.replenishment import ReplenishmentService
from src.services.reservation import ReservationService
from src.services.warehouse import Warehouse


OUTPUT_FIELDS = {
    "putaway.csv": [
        "grn_id", "line_no", "sku_id", "lot_no", "bin_id", "qty",
        "precedence_step", "rule_ids",
    ],
    "pick_lists.csv": [
        "order_id", "seq", "bin_id", "sku_id", "lot_no", "qty", "aisle",
        "walk_direction", "total_aisles_walked",
    ],
    "order_status.csv": [
        "order_id", "status", "reserved_at", "released_at", "lines_short",
        "rule_ids",
    ],
    "movements.csv": [
        "ts", "movement_type", "sku_id", "lot_no", "from_bin", "to_bin",
        "qty", "reference",
    ],
    "stock_on_hand.csv": [
        "sku_id", "lot_no", "bin_id", "qty", "status",
    ],
}


def _parse_timestamp(value):
    return datetime.fromisoformat(value.strip())


def _format_timestamp(value):
    return value.isoformat(sep=" ") if value else ""


class WarehouseApplication:
    """Runs the warehouse command stream using the shared service layer."""

    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.warehouse = Warehouse().load_warehouse(
            self.data_dir / "zones.csv",
            self.data_dir / "bins.csv",
        )

        self.grn = GRNService()
        self.grn.load_skus(self.data_dir / "skus.csv")
        self.grn.load_grn_lines(self.data_dir / "grn_lines.csv")
        self.sku_master = self.grn.skus

        self.inventory = InventoryService(self.warehouse, self.sku_master)
        self._load_opening_stock()

        self.putaway = PutawayService(
            self.warehouse, self.inventory, self.sku_master
        )
        self.reservations = ReservationService(
            self.inventory, self.sku_master
        )
        self.picking = PickingService(self.inventory, self.sku_master)
        self.pick_sequence = PickSequenceService(self.warehouse)
        self.replenishment = ReplenishmentService(
            self.inventory, self.warehouse, self.sku_master
        )
        self.expiry = ExpiryService(self.inventory, self.warehouse)
        self.cycle_count = CycleCountService(self.inventory)
        self.audit = AuditService(self.inventory)

        self.counts_by_batch = self._load_cycle_counts()
        self.received_grns = set()
        self.orders = {}
        self.putaway_rows = []
        self.pick_rows = []
        self.command_errors = []
        self.soh_snapshots = []
        self.audit_requests = []
        self.command_count = 0

    def _load_opening_stock(self):
        path = self.data_dir / "opening_stock.csv"
        with path.open(newline="", encoding="utf-8-sig") as source:
            for row_number, row in enumerate(csv.DictReader(source), start=2):
                try:
                    self.inventory.add_stock(
                        bin_id=row["bin_id"].strip(),
                        sku_id=row["sku_id"].strip(),
                        lot_no=row["lot_no"].strip(),
                        qty=int(row["qty"]),
                        grn_date=date.fromisoformat(row["grn_date"]),
                        mfg_date=(
                            date.fromisoformat(row["mfg_date"])
                            if row["mfg_date"].strip()
                            else None
                        ),
                        expiry_date=(
                            date.fromisoformat(row["expiry_date"])
                            if row["expiry_date"].strip()
                            else None
                        ),
                    )
                except (KeyError, ValueError) as error:
                    raise ValueError(
                        f"Invalid opening stock row {row_number}: {error}"
                    ) from error

        # Opening stock establishes the initial balance, not a movement in the
        # simulated command stream.
        self.inventory.movements.clear()
        self.inventory.refresh_slow_stock(date(2028, 1, 17))

    def _load_cycle_counts(self):
        batches = {}
        path = self.data_dir / "cycle_counts.csv"
        with path.open(newline="", encoding="utf-8-sig") as source:
            for row_number, row in enumerate(csv.DictReader(source), start=2):
                try:
                    count = {
                        "count_id": row["count_id"].strip(),
                        "bin_id": row["bin_id"].strip(),
                        "sku_id": row["sku_id"].strip(),
                        "lot_no": row["lot_no"].strip(),
                        "counted_qty": int(row["counted_qty"]),
                    }
                    batches.setdefault(row["count_batch"].strip(), []).append(
                        count
                    )
                except (KeyError, ValueError) as error:
                    raise ValueError(
                        f"Invalid cycle count row {row_number}: {error}"
                    ) from error
        return batches

    def run_file(self, command_file):
        path = Path(command_file)
        with path.open(encoding="utf-8-sig") as source:
            for line_number, raw_line in enumerate(source, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                self.command_count += 1
                try:
                    self.process_command(line.split("|"))
                except (KeyError, ValueError) as error:
                    self.command_errors.append({
                        "line": line_number,
                        "command": line,
                        "error": str(error),
                    })
        self.write_outputs()
        return self

    def process_command(self, fields):
        command = fields[0].strip().upper()
        handlers = {
            "RECEIVE": self._receive,
            "ORDER": self._order,
            "CONFIRM": self._confirm,
            "EOD": self._eod,
            "CYCLE_COUNT": self._cycle_count,
            "ADJUST": self._adjust,
            "PRINT_SOH": self._print_soh,
            "PRINT_AUDIT": self._print_audit,
        }
        handler = handlers.get(command)
        if handler is None:
            raise ValueError(f"Unknown command: {command}")
        handler(fields[1:])

    @staticmethod
    def _require_args(args, expected, command):
        if len(args) != expected:
            raise ValueError(
                f"{command} expects {expected} arguments; got {len(args)}"
            )

    def _receive(self, args):
        self._require_args(args, 2, "RECEIVE")
        grn_id, timestamp_text = args
        grn_id = grn_id.strip()
        timestamp = _parse_timestamp(timestamp_text)
        if grn_id in self.received_grns:
            raise ValueError(f"Duplicate receipt: {grn_id}")
        lines = self.grn.receive_grn(grn_id)
        if any(line.sku_id not in self.sku_master for line in lines):
            raise ValueError(f"GRN contains unknown SKU: {grn_id}")

        stock_before = deepcopy(self.inventory.stock)
        movement_count = len(self.inventory.movements)
        putaway_row_count = len(self.putaway_rows)
        try:
            for line in lines:
                timed_line = replace(line, grn_ts=timestamp)
                line_movement_count = len(self.inventory.movements)
                rows = self.putaway.putaway_line(timed_line, timestamp)
                for movement in self.inventory.movements[line_movement_count:]:
                    movement.movement_type = "PUTAWAY"
                self.putaway_rows.extend(rows)
        except ValueError:
            self.inventory.stock = stock_before
            del self.inventory.movements[movement_count:]
            del self.putaway_rows[putaway_row_count:]
            raise

        self.received_grns.add(grn_id)

    def _parse_order_lines(self, value):
        lines = {}
        for part in value.split(","):
            if not part.strip():
                raise ValueError("Order lines cannot contain empty entries")
            try:
                sku_id, quantity_text = part.strip().split(":", 1)
                sku_id = sku_id.strip()
                quantity = int(quantity_text)
            except ValueError:
                raise ValueError(f"Invalid order line: {part}") from None
            if sku_id not in self.sku_master:
                raise ValueError(f"Unknown SKU: {sku_id}")
            if sku_id in lines:
                raise ValueError(f"Duplicate SKU in order: {sku_id}")
            if quantity <= 0:
                raise ValueError(f"Order quantity must be positive for {sku_id}")
            lines[sku_id] = quantity
        if not lines:
            raise ValueError("Order must contain at least one line")
        return lines

    def _release_expired_reservations(self, at):
        released = self.reservations.release_expired(at)
        released_by_order = {}
        for reservation in released:
            released_by_order.setdefault(reservation.order_id, []).append(
                reservation.expires_at
            )
        for order_id, order in self.orders.items():
            if order["status"] not in {"RESERVED", "PARTIAL"}:
                continue
            active = [
                reservation
                for reservation in self.reservations.orders[order_id][
                    "reservations"
                ]
                if not reservation.released and reservation.expires_at > at
            ]
            if not active:
                order["status"] = "RELEASED"
                expirations = released_by_order.get(order_id, [])
                order["released_at"] = max(expirations) if expirations else at

    def _order(self, args):
        self._require_args(args, 6, "ORDER")
        order_id, timestamp_text, customer_id, allow_short_text, min_days, raw_lines = args
        order_id = order_id.strip()
        timestamp = _parse_timestamp(timestamp_text)
        self._release_expired_reservations(timestamp)

        if order_id in self.orders:
            raise ValueError(f"Duplicate order: {order_id}")
        allow_short_text = allow_short_text.strip().lower()
        if allow_short_text not in {"true", "false"}:
            raise ValueError("allow_short must be true or false")
        try:
            minimum_shelf_life = int(min_days) if min_days.strip() else 60
        except ValueError:
            raise ValueError("min_shelf_life_days must be an integer") from None
        if minimum_shelf_life < 0:
            raise ValueError("min_shelf_life_days cannot be negative")

        lines = self._parse_order_lines(raw_lines)
        original_minimum = self.reservations.min_shelf_life_days
        try:
            self.reservations.min_shelf_life_days = minimum_shelf_life
            reserved = self.reservations.reserve_order(
                order_id, lines, timestamp, allow_short_text == "true"
            )
        finally:
            self.reservations.min_shelf_life_days = original_minimum

        short_lines = {
            sku_id: requested - sum(
                item.qty for item in reserved if item.sku_id == sku_id
            )
            for sku_id, requested in lines.items()
        }
        short_lines = {
            sku_id: quantity for sku_id, quantity in short_lines.items()
            if quantity
        }
        rule_ids = set()
        for sku_id in lines:
            rule_ids.add(
                "FEFO" if self.sku_master[sku_id].get("expiry_tracked")
                else "FIFO"
            )
        if minimum_shelf_life:
            rule_ids.add(f"SHELF_LIFE_{minimum_shelf_life}")
        if allow_short_text == "true":
            rule_ids.add("ALLOW_SHORT")

        service_status = self.reservations.orders[order_id]["status"]
        status = "HELD" if service_status == "HOLD" else service_status
        self.orders[order_id] = {
            "customer_id": customer_id.strip(),
            "created_at": timestamp,
            "lines": lines,
            "short_lines": short_lines,
            "status": status,
            "reserved_at": timestamp if reserved else None,
            "released_at": None,
            "rule_ids": rule_ids,
            "confirmed_at": None,
        }

    def _confirm(self, args):
        self._require_args(args, 2, "CONFIRM")
        order_id, timestamp_text = args
        order_id = order_id.strip()
        timestamp = _parse_timestamp(timestamp_text)
        self._release_expired_reservations(timestamp)

        order = self.orders.get(order_id)
        if order is None:
            raise ValueError(f"Unknown order: {order_id}")
        if order["status"] in {"HELD", "RELEASED"}:
            return
        if order["confirmed_at"] is not None:
            raise ValueError(f"Order already confirmed: {order_id}")

        record = self.reservations.orders[order_id]
        active = [
            reservation for reservation in record["reservations"]
            if not reservation.released and reservation.expires_at > timestamp
        ]
        if not active:
            order["status"] = "RELEASED"
            order["released_at"] = timestamp
            return

        allocations = [
            {
                "sku_id": reservation.sku_id,
                "lot_no": reservation.lot_no,
                "bin_id": reservation.bin_id,
                "qty": reservation.qty,
            }
            for reservation in active
        ]
        self._validate_reserved_stock(allocations)

        ordered = self.pick_sequence.sequence_pick_list(allocations)
        confirmed = self.reservations.confirm_order(order_id, timestamp)
        if len(confirmed) != len(active):
            raise ValueError(f"Reservation changed while confirming {order_id}")

        total_aisles = len({
            self.warehouse.get_bin(item["bin_id"]).aisle
            for item in ordered
        })
        for item in ordered:
            self.picking.confirm_pick(
                [item], timestamp=timestamp, reference=order_id
            )
            bin_obj = self.warehouse.get_bin(item["bin_id"])
            self.pick_rows.append({
                "order_id": order_id,
                "seq": len([
                    row for row in self.pick_rows
                    if row["order_id"] == order_id
                ]) + 1,
                "bin_id": item["bin_id"],
                "sku_id": item["sku_id"],
                "lot_no": item["lot_no"],
                "qty": item["qty"],
                "aisle": bin_obj.aisle,
                "walk_direction": item["walk_direction"],
                "total_aisles_walked": total_aisles,
            })

        self.reservations.mark_picked(order_id)

        for sku_id in order["lines"]:
            movement_count = len(self.inventory.movements)
            self.replenishment.replenish(sku_id, timestamp)
            for movement in self.inventory.movements[movement_count:]:
                movement.movement_type = "REPLENISH"

        order["confirmed_at"] = timestamp
        order["status"] = (
            "PICKED_SHORT" if order["short_lines"] else "PICKED"
        )

    def _validate_reserved_stock(self, allocations):
        required = {}
        for allocation in allocations:
            key = (
                allocation["bin_id"],
                allocation["sku_id"],
                allocation["lot_no"],
            )
            required[key] = required.get(key, 0) + allocation["qty"]

        for (bin_id, sku_id, lot_no), quantity in required.items():
            if bin_id in self.inventory.frozen_bins:
                raise ValueError(f"Bin {bin_id} is frozen")
            lot = self.inventory.stock.get((bin_id, sku_id, lot_no))
            if (
                lot is None
                or lot.qty < quantity
                or lot.status not in self.inventory.PICKABLE_STATUSES
            ):
                raise ValueError(
                    f"Reserved stock is no longer available for "
                    f"{sku_id}/{lot_no} in {bin_id}"
                )

    def _eod(self, args):
        self._require_args(args, 1, "EOD")
        try:
            run_date = date.fromisoformat(args[0].strip())
        except ValueError:
            raise ValueError(f"Invalid EOD date: {args[0]}") from None
        timestamp = datetime.combine(run_date, time(23, 59, 59))

        self.inventory.refresh_slow_stock(run_date)
        quarantine_bins = {
            zone.temp_class: next(
                bin_obj.bin_id
                for bin_obj in self.warehouse.compatible_bins(
                    zone.temp_class, {"QUARANTINE"}
                )
                if bin_obj.zone_id == zone.zone_id
            )
            for zone in self.warehouse.zones.values()
        }
        movement_count = len(self.inventory.movements)
        self.expiry.quarantine_due(timestamp, quarantine_bins)
        for movement in self.inventory.movements[movement_count:]:
            movement.movement_type = "QUARANTINE"
        self._release_expired_reservations(timestamp)

    def _cycle_count(self, args):
        self._require_args(args, 2, "CYCLE_COUNT")
        batch, timestamp_text = args
        timestamp = _parse_timestamp(timestamp_text)
        counts = self.counts_by_batch.get(batch.strip())
        if counts is None:
            raise ValueError(f"Unknown cycle-count batch: {batch}")
        for count in counts:
            self.cycle_count.apply_count(
                count["bin_id"],
                count["sku_id"],
                count["counted_qty"],
                lot_no=count["lot_no"],
                timestamp=timestamp,
            )

    def _adjust(self, args):
        self._require_args(args, 2, "ADJUST")
        bin_id, timestamp_text = args
        timestamp = _parse_timestamp(timestamp_text)
        movement_count = len(self.inventory.movements)
        self.cycle_count.adjust_bin(bin_id.strip(), timestamp)
        for movement in self.inventory.movements[movement_count:]:
            movement.movement_type = "ADJUST"

    def _print_soh(self, args):
        self._require_args(args, 1, "PRINT_SOH")
        _parse_timestamp(args[0])
        rows = []
        for lot in self.inventory.stock.values():
            if lot.qty <= 0:
                continue
            rows.append({
                "sku_id": lot.sku_id,
                "lot_no": lot.lot_no,
                "bin_id": lot.bin_id,
                "qty": lot.qty,
                "status": (
                    "FROZEN" if lot.bin_id in self.inventory.frozen_bins
                    else lot.status
                ),
            })
        rows.sort(key=lambda row: (
            row["sku_id"], row["lot_no"], row["bin_id"]
        ))
        self.soh_snapshots.append(rows)

    def _print_audit(self, args):
        self._require_args(args, 1, "PRINT_AUDIT")
        sku_id = args[0].strip()
        if sku_id not in self.sku_master:
            raise ValueError(f"Unknown SKU: {sku_id}")
        self.audit_requests.append((sku_id, self.audit_rows(sku_id)))

    def _output_rows(self):
        order_rows = []
        for order_id in sorted(self.orders):
            order = self.orders[order_id]
            lines_short = ",".join(
                f"{sku_id}:{quantity}"
                for sku_id, quantity in sorted(order["short_lines"].items())
            )
            status = order["status"]
            if status in {"RESERVED", "PARTIAL"}:
                status = "CONFIRMED"
            order_rows.append({
                "order_id": order_id,
                "status": status,
                "reserved_at": _format_timestamp(order["reserved_at"]),
                "released_at": _format_timestamp(order["released_at"]),
                "lines_short": lines_short,
                "rule_ids": ";".join(sorted(order["rule_ids"])),
            })

        movement_rows = []
        for movement in self.inventory.movements:
            movement_type = movement.movement_type
            if movement_type == "TRANSFER":
                movement_type = {
                    "PICK_FACE_REPLENISHMENT": "REPLENISH",
                    "EXPIRY_QUARANTINE": "QUARANTINE",
                }.get(movement.reference, "TRANSFER")
            elif movement_type == "RECEIPT":
                movement_type = "PUTAWAY"
            elif movement_type == "ADJUSTMENT":
                movement_type = "ADJUST"
            movement_rows.append({
                "ts": _format_timestamp(movement.timestamp),
                "movement_type": movement_type,
                "sku_id": movement.sku_id,
                "lot_no": movement.lot_no,
                "from_bin": movement.from_bin or "",
                "to_bin": movement.to_bin or "",
                "qty": movement.qty,
                "reference": movement.reference,
            })

        snapshot_rows = [
            row for snapshot in self.soh_snapshots for row in snapshot
        ]
        return {
            "putaway.csv": self.putaway_rows,
            "pick_lists.csv": self.pick_rows,
            "order_status.csv": order_rows,
            "movements.csv": movement_rows,
            "stock_on_hand.csv": snapshot_rows,
        }

    def write_outputs(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for filename, rows in self._output_rows().items():
            with (self.output_dir / filename).open(
                "w", newline="", encoding="utf-8"
            ) as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=OUTPUT_FIELDS[filename],
                    extrasaction="raise",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)

    def audit_rows(self, sku_id):
        return [
            row for row in self._output_rows()["movements.csv"]
            if row["sku_id"] == sku_id
        ]
