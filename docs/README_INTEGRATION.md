# Shivashankara service modules - integration contract

Copy the `src/models` and `src/services` files into the matching folders in the team repository. These modules intentionally expose small service APIs so they can be connected to the command parser and Shivani's putaway/picking/cycle-count services.

## Shared data contract

- `Warehouse`: `zones` and `bins` dictionaries; `load_warehouse(zones_file, bins_file)`; `get_bin(bin_id)`; `compatible_bins(temp_class, bin_types)`.
- `GRNService`: call `load_skus(skus.csv)`, then `load_grn_lines(grn_lines.csv)`. Valid rows are in `grn_lines`; rejected rows (including unknown SKU such as SKU-099 in the sample) are in `rejected_rows`. `receive_grn(grn_id)` returns validated lines.
- `InventoryService`: stock keyed by `(bin_id, sku_id, lot_no)`. APIs: `add_stock`, `remove_stock`, `move_stock`, `on_hand`, `available`, `lots`, `stock_on_hand_rows`.
- `ReservationService`: `reserve_order(order_id, {sku_id: qty}, at_datetime, allow_short=False)`, `confirm_order(order_id, at_datetime)`, `release_order(order_id)`, `release_expired(at_datetime)`.
- `ReplenishmentService`: `replenish(sku_id, at_datetime)`.
- `ExpiryService`: `is_pickable(expiry_date, at_datetime)`, `blocked_lots(at_datetime)`, `quarantine_due(end_of_day_datetime, optional_temp_to_quarantine_bin_map)`.
- `ShelfLifeService`: `get_pickable_lots(sku_id, as_of, optional_minimum_shelf_life_days)`, `is_pickable(lot, as_of)`, `is_slow_moving(lot, as_of)`. The default minimum shelf life is 60 days; stock received more than 90 days earlier is slow-moving and is sorted after normal FIFO stock.
- `PickSequenceService`: `sequence_pick_list(pick_list)` orders bin allocations by ascending aisle, alternating ascending (`UP`) and descending (`DOWN`) bin numbers.
- `CycleCountService`: `apply_count(bin_id, sku_id, counted_qty, optional_lot_no, optional_timestamp)` treats `counted_qty` as the SKU total in that bin, validates the variance, and freezes the bin when it exceeds the smaller of 2% of expected quantity or 5 units. A `lot_no` is required for a positive adjustment. `adjust_bin(bin_id, optional_timestamp)` posts pending frozen-bin adjustments and unfreezes the bin; shortfalls are removed oldest-lot first.
- `AuditService`: `movement_rows`, `export_movements(path)`, `stock_snapshot`, `export_stock_on_hand(path)`, `count_variance(system_qty, counted_qty)`.

## Important integration notes

1. This is the service layer, not a complete command-file runner. The shared `main.py` / parser must call these APIs in response to RECEIVE, ORDER, CONFIRM, EOD, CYCLE_COUNT and ADJUST commands.
2. GRN loading rejects malformed rows individually so valid rows continue to load. Strict mode (`load_grn_lines(path, strict=True)`) stops on the first bad row. Do not silently put rejected GRN rows into stock.
3. Inventory requires putaway to decide a destination bin. A GRN receipt alone must not add stock to an arbitrary bin.
4. Quarantine movement requires a real `QUARANTINE` bin with matching temperature class. If no mapping is provided to `quarantine_due`, the service marks the lot QUARANTINE in place; the command runner should instead supply a mapping when physical movement is required.
5. The reservation service creates reservation records but does not physically decrement stock. Picking should consume stock after confirmation/pick execution and must check the active reservation quantities.
6. Cycle-count freeze/unfreeze orchestration belongs to the command runner and Shivani's cycle-count module. `AuditService.count_variance` returns whether the bin should freeze. Apply ADJUST only after the required authorization/state check.
7. Rule thresholds and semantics should be checked against the official brief before final submission, especially partial-order handling, split-pallet minimum, and cycle-count freeze behavior.
