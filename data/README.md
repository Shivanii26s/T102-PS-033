# PS-033 – Warehouse Putaway and Picking Engine with FIFO/FEFO and Bin Capacity — Sample Data Pack

Prepared by 10 SECONDS for Team T102.

## Files

| File | What it holds | Row count |
|---|---|---|
| `zones.csv` | 3 zones with temperature class | 3 data rows |
| `bins.csv` | 120 bins (10 aisles x 12): bins 01-03 PICK_FACE, 04-11 RESERVE, 12 QUARANTINE | 120 data rows |
| `skus.csv` | 15 SKUs with unit weight, temperature class, expiry tracking, home zone and pick-face bin | 15 data rows |
| `opening_stock.csv` | Stock by bin / SKU / lot at 2028-01-17 00:00:00 | 32 data rows |
| `grn_lines.csv` | 25 GRNs (pallet lines) — applied when the matching RECEIVE command is processed | 53 data rows |
| `cycle_counts.csv` | Cycle-count sheet in two batches | 8 data rows |
| `commands.txt` | RECEIVE, ORDER, CONFIRM, CYCLE_COUNT, ADJUST, daily EOD and print requests (40 outbound orders) | 172 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only appears in columns whose notes say so.

### `zones.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| zone_id | string | ZN-x | — | primary key |
| zone_name | string | — | — | — |
| temp_class | enum | — | AMBIENT, CHILLED | — |
| aisles | string | from-to | — | informational |

### `bins.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| bin_id | string | BIN-aa-nn | — | aa = aisle, nn = bin number; lexical order = aisle then bin |
| zone_id | string | — | zones.csv | — |
| aisle | int | — | 1-10 | — |
| bin_no | int | — | 1-12 | — |
| bin_type | enum | — | PICK_FACE, RESERVE, QUARANTINE | — |
| temp_class | enum | — | AMBIENT, CHILLED | — |
| capacity_units | int | units | — | max units regardless of SKU |
| max_weight_kg | decimal | kg | 500.00 | — |

### `skus.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| sku_id | string | SKU-nnn | — | primary key |
| description | string | — | — | — |
| unit_weight_kg | decimal | kg | — | — |
| temp_class | enum | — | AMBIENT, CHILLED | — |
| expiry_tracked | bool | — | — | true = FEFO, false = FIFO by GRN date |
| home_zone | string | — | zones.csv | — |
| pick_face_bin | string | — | bins.csv | the SKU's pick face for replenishment |

### `opening_stock.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| bin_id | string | — | bins.csv | — |
| sku_id | string | — | skus.csv | — |
| lot_no | string | LOT-... | — | — |
| qty | int | units | — | — |
| grn_date | date | — | — | FIFO date and the 90-day SLOW test |
| mfg_date | date | — | — | expiry-tracked SKUs only |
| expiry_date | date | — | — | expiry-tracked SKUs only |

### `grn_lines.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| grn_id | string | GRN-nnnn | — | one GRN has 1-3 lines |
| line_no | int | — | — | one line = one pallet |
| grn_ts | timestamp | — | — | same as the RECEIVE command |
| supplier_id | string | SUP-nn | — | — |
| sku_id | string | — | skus.csv (one planted invalid) | — |
| lot_no | string | — | — | — |
| qty | int | units | > 0 (one planted 0) | — |
| mfg_date | date | — | — | — |
| expiry_date | date | — | — | empty for non-expiry-tracked SKUs |

### `cycle_counts.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| count_id | string | CNT-nnn | — | — |
| count_batch | string | CC-nn | — | processed by CYCLE_COUNT |
| bin_id | string | — | bins.csv | — |
| sku_id | string | — | skus.csv | — |
| lot_no | string | — | — | — |
| counted_qty | int | units | — | physical count; compare with your system quantity |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two adjacent `|`) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `RECEIVE` | `grn_id|ts` | Receive all lines of the GRN and put each pallet away |
| `ORDER` | `order_id|ts|customer_id|allow_short|min_shelf_life_days|lines` | lines = `SKU:qty` joined by `,`; empty min_shelf_life_days = default 60; reserve stock |
| `CONFIRM` | `order_id|ts` | Confirm the reservation, generate the pick list and pick (then replenish pick faces) |
| `CYCLE_COUNT` | `count_batch|ts` | Apply every row of that batch from cycle_counts.csv |
| `ADJUST` | `bin_id|ts` | Post the counted variance for a frozen bin and unfreeze it |
| `EOD` | `date` | End-of-day run: expiry blocking moves to QUARANTINE, reservation expiry housekeeping |
| `PRINT_SOH` | `ts` | Print stock on hand by SKU / lot / bin |
| `PRINT_AUDIT` | `sku_id` | Print the movement audit trail for the SKU |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Pallet of 45 units into a bin with 40 units of space (remaining 5 < 10)**
  - SKU-006 lot LOT-T2-2311 already sits in BIN-02-05 with 160 of 200 units (40 free); GRN line of 45 units of the same lot -> split would leave 5 (< 10), so the whole pallet goes to the next bin — opening_stock.csv row 8 (BIN-02-05); grn_lines.csv row 3 (GRN-0002); commands.txt line 12 (`RECEIVE|GRN-0002|2028-01-20 09:30:00`)
- **EC-02 Lot expiring exactly 30 days after receipt date**
  - SKU-011 lot LOT-PN-0127 received 2028-01-27 with expiry 2028-02-26 = exactly 30 days after receipt (QUARANTINE boundary) — grn_lines.csv row 17 (GRN-0009); commands.txt line 53 (`RECEIVE|GRN-0009|2028-01-27 11:00:00`)
- **EC-03 Two lots with the same expiry date in different bins**
  - SKU-012: LOT-CH-1201 in BIN-09-07 and LOT-CH-1202 in BIN-09-05 share expiry 2028-04-29 -> FEFO tie broken by lowest bin ID (BIN-09-05 first); order needs 40 so both are used — opening_stock.csv row 29 (BIN-09-07); opening_stock.csv row 28 (BIN-09-05); commands.txt line 18 (`ORDER|OUT-0001|2028-01-21 10:15:00|CUST-132|false|30|SKU-012:40`); commands.txt line 19 (`CONFIRM|OUT-0001|2028-01-21 12:15:00`)
- **EC-04 Order requiring 60 days shelf life when only a 59-day lot exists**
  - SKU-013: the only lot LOT-CR-0110 expires 2028-04-01 = 59 days after the 2028-02-02 order that demands 60 days -> skipped; allow_short=false so the whole order is held — opening_stock.csv row 31 (BIN-10-06); commands.txt line 80 (`ORDER|OUT-0017|2028-02-02 09:00:00|CUST-130|false|60|SKU-013:20`); commands.txt line 82 (`CONFIRM|OUT-0017|2028-02-02 10:00:00`)
- **EC-05 Reservation expiring at the exact moment a second order is placed**
  - SKU-003 (40 units in total): order at 2028-01-24 10:00:00 reserves 30 and is never confirmed; second order for 30 arrives at 2028-01-26 10:00:00 = exactly 48 h later — commands.txt line 30 (`ORDER|OUT-0004|2028-01-24 10:00:00|CUST-128|false|30|SKU-003:30`); commands.txt line 43 (`ORDER|OUT-0009|2028-01-26 10:00:00|CUST-136|false|30|SKU-003:30`); commands.txt line 46 (`CONFIRM|OUT-0009|2028-01-26 13:00:00`)
- **EC-06 Pick face drops to exactly 20% capacity**
  - SKU-007: pick face BIN-01-02 (capacity 100) holds 50 of the same lot as reserve BIN-01-11; pick of 30 leaves exactly 20 = 20% (no replenishment); the next pick of 1 drops it to 19 -> replenish to 80 — opening_stock.csv row 2 (BIN-01-02); commands.txt line 24 (`ORDER|OUT-0003|2028-01-22 14:00:00|CUST-119|true|30|SKU-007:30`); commands.txt line 25 (`CONFIRM|OUT-0003|2028-01-22 14:30:00`); commands.txt line 36 (`ORDER|OUT-0007|2028-01-25 11:00:00|CUST-130|false|30|SKU-007:1`); commands.txt line 37 (`CONFIRM|OUT-0007|2028-01-25 11:30:00`)
- **EC-07 Cycle count variance of exactly 2% on a 100-unit bin**
  - Count batch CC-01 on 2028-01-18: BIN-06-10 holds 100 units, counted 98 = exactly 2% / 2 units (not 'more than') -> no freeze — cycle_counts.csv row 1 (CNT-001); opening_stock.csv row 20 (BIN-06-10); commands.txt line 5 (`CYCLE_COUNT|CC-01|2028-01-18 08:00:00`)
- **EC-08 End-of-day run on 29 Feb with a lot expiring 7 days later**
  - SKU-014 lot LOT-ML-1110 expires 2028-03-07: from 00:00 on 2028-02-29 it has 7 days left -> unpickable (the 2028-02-29 order must take LOT-ML-1205), and the EOD run of 2028-02-29 moves it to QUARANTINE — opening_stock.csv row 24 (BIN-08-06); commands.txt line 181 (`ORDER|OUT-0035|2028-02-29 10:00:00|CUST-129|true|30|SKU-014:25`); commands.txt line 183 (`CONFIRM|OUT-0035|2028-02-29 11:00:00`); commands.txt line 190 (`EOD|2028-02-29`)
- **Extra traps (not in the brief, but realistic):**
  - Second order for the same SKU with an empty min_shelf_life (default 60) and allow_short=true -> ships the other line only — commands.txt line 81 (`ORDER|OUT-0018|2028-02-02 09:20:00|CUST-133|true||SKU-013:10,SKU-008:5`); commands.txt line 83 (`CONFIRM|OUT-0018|2028-02-02 10:20:00`)
  - SKU-001 is 25 kg per bag: a 24-bag pallet is 600 kg > 500 kg bin weight limit -> at most 20 bags per bin; the 4-bag remainder (< 10) cannot be split off — grn_lines.csv row 29 (GRN-0015); commands.txt line 104 (`RECEIVE|GRN-0015|2028-02-08 08:45:00`)
  - SKU-002 (not expiry-tracked) lot LOT-SC-0815 was received 2027-08-15, more than 90 days before the period -> SLOW, moved to the back of the FIFO sequence behind LOT-SC-1210 — opening_stock.csv row 16 (BIN-05-09); opening_stock.csv row 13 (BIN-05-06)
  - GRN with a line for SKU-099 (not in skus.csv) and a line with quantity 0 -> reject both lines — grn_lines.csv row 37 (GRN-0019); commands.txt line 128 (`RECEIVE|GRN-0019|2028-02-15 10:00:00`); grn_lines.csv row 38 (GRN-0019); commands.txt line 128 (`RECEIVE|GRN-0019|2028-02-15 10:00:00`)
  - The 2028-01-27 GRN is RECEIVEd twice (scanner re-sync) -> the second RECEIVE must be rejected, not double-counted — commands.txt line 53 (`RECEIVE|GRN-0009|2028-01-27 11:00:00`); commands.txt line 54 (`RECEIVE|GRN-0009|2028-01-27 11:12:00`)
  - Same batch: BIN-06-07 system 120, counted 114 (6 units > 5) -> bin frozen until ADJUST; shortfall reduces the oldest lot first; BIN-06-08 counted 2 units over — cycle_counts.csv row 2 (CNT-002); cycle_counts.csv row 3 (CNT-003); commands.txt line 6 (`ADJUST|BIN-06-07|2028-01-18 11:00:00`)

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `putaway.csv`

One row per bin a pallet (or part) is put into, in processing order.

Columns, in order: `grn_id`, `line_no`, `sku_id`, `lot_no`, `bin_id`, `qty`, `precedence_step`, `rule_ids`

### `pick_lists.csv`

One row per pick line per confirmed order, in pick sequence.

Columns, in order: `order_id`, `seq`, `bin_id`, `sku_id`, `lot_no`, `qty`, `aisle`, `walk_direction`, `total_aisles_walked`

### `order_status.csv`

One row per order after all commands.

Columns, in order: `order_id`, `status`, `reserved_at`, `released_at`, `lines_short`, `rule_ids`

### `movements.csv`

Audit trail: every stock movement in processing order (PUTAWAY, PICK, REPLENISH, QUARANTINE, ADJUST).

Columns, in order: `ts`, `movement_type`, `sku_id`, `lot_no`, `from_bin`, `to_bin`, `qty`, `reference`

### `stock_on_hand.csv`

One row per bin/SKU/lot with qty > 0 at PRINT_SOH, sorted by sku_id, lot_no, bin_id.

Columns, in order: `sku_id`, `lot_no`, `bin_id`, `qty`, `status`

Binding choices: remaining shelf life = expiry_date - order date in days; 'within 30 days of receipt' compares expiry_date - receipt date in days; `walk_direction` is UP or DOWN; `status` (orders) is CONFIRMED, HELD, RELEASED, PICKED or PICKED_SHORT; `status` (stock) is AVAILABLE, RESERVED, FROZEN, SLOW, BLOCKED or QUARANTINE; empty from_bin/to_bin means outside the warehouse.
