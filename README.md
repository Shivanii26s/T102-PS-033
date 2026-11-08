# Warehouse Putaway and Picking Engine

## Overview

T102-PS-033 is a Python command-file-driven warehouse application for receiving
goods, storing inventory, reserving and picking customer orders, replenishing
pick faces, handling expiry and cycle counts, and producing CSV reports. The
command runner reads warehouse master data and an ordered stream of simulated
commands, then writes five CSV outputs.

The application is a command-line program. It does not provide a website or
graphical user interface.

## Problem statement and objectives

Warehouse operations must place incoming pallets in suitable bins while
respecting temperature, capacity, weight, and lot rules. Outbound orders need
available stock selected in the right order, with shelf-life and reservation
requirements enforced. The system also needs an auditable record of inventory
movements and a way to manage expiring and discrepant stock.

Project objectives:

- Process warehouse commands in file order using their supplied simulated
  timestamps.
- Apply putaway, capacity, FIFO/FEFO, shelf-life, reservation, replenishment,
  expiry, quarantine, and cycle-count rules.
- Produce consistent putaway, pick, order, movement, and stock-on-hand CSV
  reports.
- Exercise the service layer and end-to-end command stream with automated
  tests.

## Technologies

- Python 3.10 or later
- Python standard library: `argparse`, `csv`, `dataclasses`, `datetime`, and
  `pathlib`
- pytest 9.2.0 for automated tests

The application itself uses only the Python standard library. pytest is listed
in `requirements.txt` for test execution.

## Implemented features and business rules

- Loads zones, bins, SKUs, GRN lines, opening stock, and cycle counts from CSV.
- Processes `RECEIVE`, `ORDER`, `CONFIRM`, `EOD`, `CYCLE_COUNT`, `ADJUST`,
  `PRINT_SOH`, and `PRINT_AUDIT`.
- Validates warehouse temperature compatibility and bin unit and weight
  capacity; a bin is limited to two distinct SKUs.
- Places normal stock using same-lot, empty home-zone, then other empty
  compatible-bin precedence. Expiry-due receipts are routed to compatible
  quarantine bins. Pallets are not split when the remainder would be fewer
  than 10 units.
- Selects non-expiry-tracked stock FIFO by GRN date, with slow-moving stock
  sorted after normal stock. Expiry-tracked stock uses FEFO; equal expiry dates
  are broken by bin ID.
- Applies minimum remaining shelf life to expiry-tracked order lines. The
  default is 60 days; orders can specify another minimum.
- Reserves stock for up to 48 hours until confirmed or released. Confirmed
  orders consume their reserved stock when picked, after which those
  reservations no longer lock stock.
- Uses an aisle-ordered serpentine pick sequence with alternating bin
  direction. After a successful pick, a pick face below 20% of its unit
  capacity is replenished toward 80%, subject to capacity and weight limits.
  Replenishment uses FIFO/FEFO order and only eligible reserve bins.
- Blocks expiry-tracked stock with seven or fewer days remaining from picking.
  End-of-day processing physically moves due stock to a temperature-compatible
  quarantine bin.
- Compares cycle counts against SKU totals per bin. A variance freezes a bin
  when its absolute value exceeds the smaller of 2% of expected quantity or
  five units. Shortfalls are adjusted from the oldest lot first; `lot_no` is
  retained to attribute a positive adjustment.
- Rejects duplicate GRN receipts. Invalid commands are reported, and processing
  continues with later commands.

## Project structure

```text
.
├── data/                   # Warehouse CSV inputs and sample command stream
├── docs/                   # Integration notes and design document
├── output/                 # Five generated CSV reports
├── src/
│   ├── application.py      # Data loading, command dispatch, output writing
│   ├── models/             # Stock, movement, reservation, and order entities
│   └── services/           # Warehouse business-rule services
├── tests/                  # Unit and command-runner integration tests
├── main.py                 # CLI entry point
├── pytest.ini              # pytest project path configuration
└── requirements.txt        # Test dependency
```

The repository also contains root-level `inventory.py`, `movement.py`,
`picking.py`, `reservation.py`, and `warehouse.py` prototype modules. The active
command-line application is `main.py`, which imports and runs
`src.application.WarehouseApplication`.

## Setup and installation

Create and activate a virtual environment, then install the test dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
Python 3.10 or later is required.

## Run the application

From the project root, run the sample command file with the existing CLI:

```bash
python main.py
```

By default, the application reads `data/commands.txt`, loads input CSV files
from `data/`, and writes reports to `output/`. To supply a different command
file or directories:

```bash
python main.py path/to/commands.txt --data-dir path/to/data --output-dir path/to/output
```

Command lines are processed in file order. Blank lines and lines beginning
with `#` are ignored. Rejected commands are reported to stderr; the runner
continues processing subsequent commands and writes outputs for successful
operations. The CLI currently returns a successful process exit code even if
one or more commands were rejected, so check stderr when validating a run.

## Run tests

```bash
pytest -q
```

The test suite includes service-level tests and integration tests that run the
sample command stream and check command handling and CSV contracts.

## Generated CSV outputs

The CLI writes the following files to the output directory:

| File | Contents |
|---|---|
| `putaway.csv` | One row for each bin used for a received pallet or pallet portion, in processing order. |
| `pick_lists.csv` | Pick allocations for confirmed orders, in serpentine pick sequence. |
| `order_status.csv` | Final status, reservation/release times, short lines, and rule IDs for each order. |
| `movements.csv` | Stock movement audit trail in processing order: putaway, pick, replenishment, quarantine, and adjustment. |
| `stock_on_hand.csv` | Positive-quantity bin/SKU/lot rows captured at `PRINT_SOH`, sorted by SKU, lot, and bin. |

Exact column names and order are defined in
[`data/README.md`](data/README.md) and implemented in
[`src/application.py`](src/application.py).

## Team contributions

Based on the project’s existing integration documentation and source history:

- **Shivani** — putaway and picking work, pick sequencing and cycle-count
  services, and integration of the command-line application and its tests.
- **Shivashankara** — shared warehouse service layer and service integration,
  including warehouse, inventory, GRN, expiry, and audit functionality.
