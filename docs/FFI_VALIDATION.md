# Validating W's C Interoperability

- **Status:** The SQLite pilot and CSV import flow are implemented; a production profile has not been approved.
- **Date:** 2026-10-16

## Pilot workflow

`examples/ffi/sqlite/import_csv.w` imports measurements into a persistent local database. It validates columns, 64-bit ASCII integers, and bounds; uses a transaction; returns data or SQLite errors; and closes its resources. `import_reference.c` independently implements the same contract with the same C adapter and library. There is not yet a real user workload or a measured time saving; product validation remains open.

The input format requires the exact header `id,value` and accepts up to 100,000 rows. Both columns are non-negative decimal integers in `[0, INT64_MAX]`. The parser accepts LF, CRLF, and a final line without a newline. It rejects quotes, empty fields, signs, Unicode digits, NUL, and extra columns; this is not a general CSV parser. The identifier is a primary key, so duplicates in the batch or database abort the whole batch. The aggregate sum must also fit in int64; it is checked before commit, and SQLite overflow rolls back the import.

A valid import persists its rows. An invalid import preserves the exact set of rows that existed before the batch. Data and SQLite errors return exit status 1; usage or read errors return 2; success returns 0. `--version` prints the linked SQLite version.

## Ownership and adapter costs

The FFI carries scalars and `opaque` handles, not W strings or buffers. The database path comes from `W_SQLITE_DB`. `adapter.c` owns fixed SQL statements, the connection, and prepared statements; this adapter is product code that must be maintained. `pilot_close` closes statements and the connection, and `pilot_dispose` frees the control block. Repeated close is valid; use after close returns `SQLITE_MISUSE`. Using a handle after destruction or destroying it twice remains an unsafe error that W does not prevent.

The W helper that acquires the resource routes every later exit through one cleanup point. Errors returned by `populate` are handled before leaving. This pilot does not require a new `defer/with` construct. External counters check that connections, control blocks, and statements are no longer live. `W_MEM_CHECK` checks only W allocations on normal exit; `exit()` bypasses that check. Sanitizers and external counters are needed for this CLI, which returns process exit codes.

## Reproducing the checks

A C99 compiler, SQLite headers, and `libsqlite3` are required. Linux CI installs `libsqlite3-dev`; macOS uses the system SDK and library.

```sh
python3 tools/validate_sqlite_ffi.py --sanitize
python3 tools/validate_sqlite_import.py --sanitize --rows 1000 --samples 1
python3 tools/validate_sqlite_import.py --rows 10000 --samples 3 --report .w_cache/sqlite-import/optimized.json
python3 tools/measure_tokenizer.py
```

To run the importer from the repository root:

```sh
mkdir -p .w_cache/sqlite-import
cc -std=c99 -O2 -c examples/ffi/sqlite/adapter.c -o .w_cache/sqlite-import/adapter.o
./w build examples/ffi/sqlite/import_csv.w --link-lib .w_cache/sqlite-import/adapter.o --link-lib sqlite3 -o .w_cache/sqlite-import/import_csv
W_SQLITE_DB=.w_cache/sqlite-import/measurements.sqlite .w_cache/sqlite-import/import_csv measurements.csv
```

The runner tests C, AST, and HIR, then invokes W1 directly without running the W0 checker over the input. An independent Python connection compares persisted rows rather than checking output alone. The test appends data in a second run and exercises 14 failures, including an error after an earlier valid row has been inserted. It requires rollback, the expected exit status, no live external resources, and no sanitizer output. Linux enables LSan; macOS does not support it. The system SQLite library is not rebuilt with sanitizers. The earlier `measurements.w` pilot retains C/AST/HIR checks for repeated close and use after close.

## Measurement and interpretation

Each JSON report records the compiler, platform, linked SQLite version, flags, commands, build time for each program, samples, binary size, and peak resident memory. The shared adapter build is excluded from each program's runtime; the W1 bootstrap is reported separately. One warm-up run is discarded.

`tools/measure_process.py` runs exactly one child in a fresh measurement process, so `ru_maxrss` does not inherit peaks from previous runs. Darwin reports bytes and Linux reports KiB; both are converted to bytes. Time includes process startup, SQLite, and I/O, but excludes launching the Python helper. RSS and binary size depend on platform, flags, and SDK. These numbers describe the full workflow, not the isolated cost of the FFI.

W provides typed errors and control flow, but this pilot still needs a manual adapter and has higher representation costs than C. It validates one concrete integration path; it does not establish a general performance advantage or production readiness.
