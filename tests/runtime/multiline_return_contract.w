fn number() -> int {
    return
        40 + 2
}
fn empty() -> unit { return }
fn failed() -> int ! str {
    return
        Err("multiline")
}
fn absent() -> int? {
    return
        none
}
print(number(), empty(), absent())
print(failed() else error { print(error)
    0
})
