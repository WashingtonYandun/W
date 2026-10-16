# ERROR: W2004
fn f(x: int) -> int {
    match x { 1 => { return 7 } }
    print("fallthrough")
}
print(f(2))
