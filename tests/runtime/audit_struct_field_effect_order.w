struct Pair { a: int, b: int }
fn mark(x: int) -> int { print(x)
    return x
}
let p = Pair { b: mark(2), a: mark(1) }
print(p.a, p.b)
