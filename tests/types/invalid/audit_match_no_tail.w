# ERROR: W2004
fn f(x: int) -> int {
    match x { 1 => { return 7 } }
    let unused = 0
}
print(f(2))
