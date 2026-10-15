# W assignment is an expression: `a = b = 5` and `let x = a = 7` are legal because `=`
# has a precedence level and right associativity. The HIR has no assignment expression
# node, so this fixture pins the lowering: the value must be captured before an enclosing
# assignment overwrites the target, and the emitted temporaries must be consistently named.
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

    # A three-level chain (`d = e = f = 9`) is rejected with W2013: the HIR has no
    # assignment expression node, so each level synthesises a temporary, and only one
    # nested level is verified. Split chains instead.
}

main()
