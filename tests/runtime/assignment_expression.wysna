# Assignment expressions preserve their value before enclosing writes.
fn assign_chain() -> tuple[int, int] {
    let mut a = 0
    let mut b = 0
    a = b = 5
    return (a, b)
}

fn main() {
    let first = assign_chain()
    print(first)

    let mut c = 0
    let captured = c = 7
    print(c, captured)


}

main()
