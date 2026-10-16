# ERROR: W2004
fn f(x: int) -> list[int] {
    match x { 1 => { return [7] } }
    let unused = 0
}
for item in f(2) { print(item) }
