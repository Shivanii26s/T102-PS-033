import argparse
from pathlib import Path
import sys

from src.application import WarehouseApplication


def main(argv=None):
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Process a warehouse command file using CSV input data."
    )
    parser.add_argument(
        "command_file",
        nargs="?",
        type=Path,
        default=project_dir / "data" / "commands.txt",
        help="command stream (defaults to data/commands.txt)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_dir / "data",
        help="directory containing warehouse CSV input files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_dir / "output",
        help="directory for generated CSV outputs (defaults to output/)",
    )
    args = parser.parse_args(argv)

    application = WarehouseApplication(args.data_dir, args.output_dir)
    application.run_file(args.command_file)

    for error in application.command_errors:
        print(
            f"Rejected command on line {error['line']}: {error['error']}",
            file=sys.stderr,
        )
    for sku_id, rows in application.audit_requests:
        print(f"Audit trail for {sku_id}:")
        for row in rows:
            print(
                " | ".join(str(row[field]) for field in (
                    "ts", "movement_type", "sku_id", "lot_no",
                    "from_bin", "to_bin", "qty", "reference",
                ))
            )

    print(
        f"Processed {application.command_count} commands from "
        f"{args.command_file}"
    )
    print(f"CSV outputs written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
