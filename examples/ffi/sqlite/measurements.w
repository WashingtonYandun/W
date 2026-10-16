extern "C" fn pilot_open() -> opaque
extern "C" fn pilot_is_open(handle: opaque) -> bool
extern "C" fn pilot_status(handle: opaque) -> int32
extern "C" fn pilot_begin(handle: opaque) -> int32
extern "C" fn pilot_insert(handle: opaque, id: int64, value: int64) -> int32
extern "C" fn pilot_commit(handle: opaque) -> int32
extern "C" fn pilot_count(handle: opaque) -> int64
extern "C" fn pilot_total(handle: opaque) -> int64
extern "C" fn pilot_close(handle: opaque) -> int32
extern "C" fn pilot_dispose(handle: opaque) -> int32
extern "C" fn pilot_live_resources() -> int32
extern "C" fn pilot_version() -> int32
extern "C" fn pilot_rows() -> int64

struct DatabaseError { code: int }
struct InputError { code: int }

fn insert(handle: opaque, id: int, value: int) -> int ! DatabaseError | InputError {
    if value < 0 { return Err(InputError { code: -1 }) }
    let status = pilot_insert(handle, id, value)
    if status != 0 { return Err(DatabaseError { code: status }) }
    return 0
}

fn error_code(handle: opaque, id: int, value: int) -> int {
    return insert(handle, id, value) else err {
        match err {
            DatabaseError(error) => error.code,
            InputError(error) => error.code
        }
    }
}

fn populate(handle: opaque, rows: int) -> int {
    let started = pilot_begin(handle)
    if started != 0 { return started }
    for id in 0..rows {
        let status = error_code(handle, id, 4294967296 + id * 10)
        if status != 0 { return status }
    }
    return pilot_commit(handle)
}

fn main() -> unit {
    let handle = pilot_open()
    let rows = pilot_rows()
    if not pilot_is_open(handle) or rows < 1 {
        print("open or input failure", pilot_status(handle), rows)
        print(pilot_dispose(handle), pilot_live_resources())
        return
    }
    let status = populate(handle, rows)
    if status != 0 {
        print("populate failure", status)
        print(pilot_dispose(handle), pilot_live_resources())
        return
    }
    print(pilot_version())
    print(pilot_count(handle), pilot_total(handle))
    let duplicate = error_code(handle, 0, 1)
    let invalid = error_code(handle, rows, -1)
    let closed = pilot_close(handle)
    let after_close = error_code(handle, rows, 1)
    let closed_again = pilot_close(handle)
    let disposed = pilot_dispose(handle)
    print(duplicate, invalid, after_close, closed, closed_again, disposed, pilot_live_resources())
}

main()
