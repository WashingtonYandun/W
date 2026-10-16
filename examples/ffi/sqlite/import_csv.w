extern "C" fn pilot_version() -> int32
extern "C" fn pilot_open() -> opaque
extern "C" fn pilot_is_open(handle: opaque) -> bool
extern "C" fn pilot_status(handle: opaque) -> int32
extern "C" fn pilot_begin(handle: opaque) -> int32
extern "C" fn pilot_insert(handle: opaque, id: int64, value: int64) -> int32
extern "C" fn pilot_commit(handle: opaque) -> int32
extern "C" fn pilot_rollback(handle: opaque) -> int32
extern "C" fn pilot_count(handle: opaque) -> int64
extern "C" fn pilot_total(handle: opaque) -> int64
extern "C" fn pilot_dispose(handle: opaque) -> int32
extern "C" fn pilot_live_resources() -> int32

struct CsvError { line: int, reason: str }
struct DatabaseError { code: int }

fn decimal(text: str, line: int) -> int ! CsvError {
    if len(text) == 0 { return Err(CsvError { line: line, reason: "empty integer" }) }
    let mut value = 0
    for index in 0..len(text) {
        let digit = ord(text[index]) - ord("0")
        if digit < 0 or digit > 9 { return Err(CsvError { line: line, reason: "expected ASCII decimal" }) }
        if value > (9223372036854775807 - digit) / 10 {
            return Err(CsvError { line: line, reason: "integer overflow" })
        }
        value = value * 10 + digit
    }
    return value
}

fn insert_line(handle: opaque, text: str, line: int) -> unit ! CsvError | DatabaseError {
    let mut comma = -1
    for index in 0..len(text) {
        if text[index] == "," {
            if comma >= 0 { return Err(CsvError { line: line, reason: "expected two columns" }) }
            comma = index
        }
    }
    if comma < 0 { return Err(CsvError { line: line, reason: "expected two columns" }) }
    let id = decimal(slice(text, 0, comma), line)?
    let value = decimal(slice(text, comma + 1, len(text)), line)?
    let status = pilot_insert(handle, id, value)
    if status != 0 { return Err(DatabaseError { code: status }) }
}

fn populate(handle: opaque, text: str) -> int ! CsvError | DatabaseError {
    let started = pilot_begin(handle)
    if started != 0 { return Err(DatabaseError { code: started }) }
    let mut start = 0
    let mut line = 1
    let mut rows = 0
    for index in 0..=len(text) {
        if index == len(text) or text[index] == "\n" {
            if index == len(text) and start == index { break }
            let mut end = index
            if end > start and text[end - 1] == "\r" { end = end - 1 }
            let content = slice(text, start, end)
            if line == 1 {
                if content != "id,value" { return Err(CsvError { line: line, reason: "expected id,value header" }) }
            } else {
                if rows >= 100000 { return Err(CsvError { line: line, reason: "row limit exceeded" }) }
                insert_line(handle, content, line)?
                rows = rows + 1
            }
            line = line + 1
            start = index + 1
        }
    }
    if rows == 0 { return Err(CsvError { line: line, reason: "no measurements" }) }
    let total = pilot_total(handle)
    let summary_status = pilot_status(handle)
    if summary_status != 0 { return Err(DatabaseError { code: summary_status }) }
    let status = pilot_commit(handle)
    if status != 0 { return Err(DatabaseError { code: status }) }
    return rows
}

fn run() -> int {
    let arguments = args()
    if len(arguments) == 2 and arguments[1] == "--version" { print(pilot_version())
        return 0
    }
    if len(arguments) != 2 { print("usage: import_csv measurements.csv (W_SQLITE_DB selects database)")
        return 2
    }
    let text = read_file(arguments[1]) else error { print("io error", error)
        return 2
    }
    let handle = pilot_open()
    if not pilot_is_open(handle) {
        print("database error", pilot_status(handle))
        let closed = pilot_dispose(handle)
        print("resources", pilot_live_resources())
        return 1
    }
    let imported = populate(handle, text) else error {
        match error {
            CsvError(detail) => { print("csv error", detail.line, detail.reason) },
            DatabaseError(detail) => { print("database error", detail.code) }
        }
        let rollback = pilot_rollback(handle)
        if rollback != 0 { print("rollback error", rollback) }
        let failure = -1
        failure
    }
    if imported >= 0 { print("imported", imported, pilot_count(handle), pilot_total(handle)) }
    let closed = pilot_dispose(handle)
    print("resources", pilot_live_resources())
    if closed != 0 or imported < 0 { return 1 }
    return 0
}

fn main() -> unit {
    let status = run()
    exit(status)
}

main()
