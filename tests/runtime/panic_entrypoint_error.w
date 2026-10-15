# RUNTIME_PANIC: W4003
# An unhandled `Err` from main must reach the process exit status and stderr.
fn main() -> unit ! IoError {
    let content = read_file("/nonexistent/w-audit-probe.txt")?
    print(len(content))
    return
}

main()
