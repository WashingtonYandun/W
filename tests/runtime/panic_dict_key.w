# RUNTIME_PANIC: W4002
fn main() {
    let table = {"a": 1}
    print(table["missing"])
}

main()
