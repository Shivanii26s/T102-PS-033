import csv
from pathlib import Path

from src.application import OUTPUT_FIELDS, WarehouseApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"


def make_application(tmp_path):
    return WarehouseApplication(DATA_DIR, tmp_path / "output")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def test_receive_duplicate_is_rejected_without_double_counting(tmp_path):
    app = make_application(tmp_path)
    app.process_command(["RECEIVE", "GRN-0001", "2028-01-19 10:00:00"])
    stock_after_first_receipt = {
        key: lot.qty for key, lot in app.inventory.stock.items()
    }

    try:
        app.process_command(
            ["RECEIVE", "GRN-0001", "2028-01-20 10:00:00"]
        )
    except ValueError as error:
        assert "Duplicate receipt" in str(error)
    else:
        raise AssertionError("A duplicate receipt was accepted")

    assert {
        key: lot.qty for key, lot in app.inventory.stock.items()
    } == stock_after_first_receipt
    assert len(app.putaway_rows) == 2


def test_cycle_count_keeps_lot_context_and_adjusts_frozen_bin(tmp_path):
    app = make_application(tmp_path)
    app.process_command(
        ["CYCLE_COUNT", "CC-01", "2028-01-18 08:00:00"]
    )

    pending = app.cycle_count.pending_counts["BIN-06-07"]["SKU-009"]
    assert pending["lot_no"] == "LOT-DT-1104"
    assert "BIN-06-07" in app.inventory.frozen_bins

    app.process_command(["ADJUST", "BIN-06-07", "2028-01-18 11:00:00"])

    assert app.inventory.on_hand("SKU-009", "BIN-06-07") == 114
    assert "BIN-06-07" not in app.inventory.frozen_bins
    assert app.inventory.movements[-1].movement_type == "ADJUST"


def test_order_does_not_reserve_stock_from_a_frozen_bin(tmp_path):
    app = make_application(tmp_path)
    app.inventory.frozen_bins.add("BIN-01-01")

    app.process_command([
        "ORDER", "ORDER-1", "2028-01-20 10:00:00", "CUSTOMER-1",
        "false", "60", "SKU-004:1",
    ])

    reservations = app.reservations.orders["ORDER-1"]["reservations"]
    assert reservations
    assert all(
        reservation.bin_id != "BIN-01-01" for reservation in reservations
    )


def test_ec06_picked_order_replenishes_pick_face_and_consumes_reservation(
    tmp_path,
):
    app = make_application(tmp_path)
    command_lines = (DATA_DIR / "commands.txt").read_text(
        encoding="utf-8-sig"
    ).splitlines()

    for line_number in (24, 25):
        app.process_command(command_lines[line_number - 1].split("|"))

    first_order_reservation = next(
        reservation for reservation in app.reservations.reservations
        if reservation.order_id == "OUT-0003"
    )
    assert first_order_reservation.released is True
    assert app.inventory.on_hand("SKU-007", "BIN-01-02") == 20
    assert not any(
        movement.movement_type == "REPLENISH"
        for movement in app.inventory.movements
    )

    for line_number in (36, 37):
        app.process_command(command_lines[line_number - 1].split("|"))

    second_order_pick = next(
        row for row in app.pick_rows if row["order_id"] == "OUT-0007"
    )
    assert second_order_pick["bin_id"] == "BIN-01-02"
    assert second_order_pick["qty"] == 1
    assert app.inventory.on_hand("SKU-007", "BIN-01-02") == 80
    assert app.inventory.on_hand("SKU-007", "BIN-01-11") == 89

    replenish_movements = [
        movement for movement in app.inventory.movements
        if movement.movement_type == "REPLENISH"
    ]
    assert len(replenish_movements) == 1
    assert (
        replenish_movements[0].from_bin,
        replenish_movements[0].to_bin,
        replenish_movements[0].qty,
        replenish_movements[0].reference,
    ) == (
        "BIN-01-11",
        "BIN-01-02",
        61,
        "PICK_FACE_REPLENISHMENT",
    )


def test_all_sample_commands_produce_contract_csv_outputs(tmp_path):
    app = make_application(tmp_path)
    app.run_file(DATA_DIR / "commands.txt")

    assert app.command_count == 172
    assert {error["line"] for error in app.command_errors} == {54, 104, 128}
    assert len(app.orders) == 40
    assert len(app.audit_requests) == 15
    assert len(app.soh_snapshots) == 1

    output_dir = tmp_path / "output"
    output_rows = {}
    for filename, expected_fields in OUTPUT_FIELDS.items():
        fields, rows = read_csv(output_dir / filename)
        assert fields == expected_fields
        output_rows[filename] = rows

    putaway = output_rows["putaway.csv"]
    assert [
        row["bin_id"] for row in putaway if row["grn_id"] == "GRN-0002"
    ] == ["BIN-05-01"]
    assert not any(row["grn_id"] == "GRN-0015" for row in putaway)
    assert len([
        row for row in putaway if row["grn_id"] == "GRN-0009"
    ]) == 2

    statuses = {
        row["order_id"]: row for row in output_rows["order_status.csv"]
    }
    assert statuses["OUT-0004"]["status"] == "RELEASED"
    assert statuses["OUT-0004"]["released_at"] == "2028-01-26 10:00:00"
    assert statuses["OUT-0017"]["status"] == "HELD"
    assert statuses["OUT-0018"]["status"] == "PICKED_SHORT"
    assert statuses["OUT-0035"]["status"] == "PICKED"

    picks = output_rows["pick_lists.csv"]
    assert [
        row["lot_no"] for row in picks if row["order_id"] == "OUT-0035"
    ] == ["LOT-ML-1205"]
    for order_id in {row["order_id"] for row in picks}:
        order_picks = [row for row in picks if row["order_id"] == order_id]
        assert [int(row["aisle"]) for row in order_picks] == sorted(
            int(row["aisle"]) for row in order_picks
        )
        assert [int(row["seq"]) for row in order_picks] == list(
            range(1, len(order_picks) + 1)
        )

    movements = output_rows["movements.csv"]
    assert {row["movement_type"] for row in movements} <= {
        "PUTAWAY", "PICK", "REPLENISH", "QUARANTINE", "ADJUST"
    }
    assert any(
        row["movement_type"] == "QUARANTINE"
        and row["lot_no"] == "LOT-ML-1110"
        for row in movements
    )
    assert all(row["ts"].startswith("2028-") for row in movements)

    stock = output_rows["stock_on_hand.csv"]
    assert [
        (row["sku_id"], row["lot_no"], row["bin_id"]) for row in stock
    ] == sorted(
        (row["sku_id"], row["lot_no"], row["bin_id"]) for row in stock
    )
    assert any(
        row["bin_id"] == "BIN-06-08" and row["status"] == "FROZEN"
        for row in stock
    )


def test_print_audit_captures_rows_at_command_time(tmp_path):
    app = make_application(tmp_path)
    command_file = tmp_path / "commands.txt"
    command_file.write_text(
        "PRINT_AUDIT|SKU-001\n"
        "RECEIVE|GRN-0005|2028-01-21 09:15:00\n",
        encoding="utf-8",
    )

    app.run_file(command_file)

    assert app.audit_requests == [("SKU-001", [])]
    assert any(
        movement.sku_id == "SKU-001" for movement in app.inventory.movements
    )


def test_opening_stock_load_does_not_create_wall_clock_movements(tmp_path):
    app = make_application(tmp_path)

    assert app.inventory.movements == []
    assert app.inventory.on_hand("SKU-009", "BIN-06-10") == 100
    assert app.inventory.stock[
        ("BIN-05-09", "SKU-002", "LOT-SC-0815")
    ].status == "SLOW"
