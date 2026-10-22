struct Box[T] {
    val: T
}

struct Pair[A, B] {
    first: A,
    second: B
}

fn make_pair[A, B](a: A, b: B) -> Pair[A, B] {
    return Pair[A, B] { first: a, second: b }
}

let p1 = make_pair(10, "ten")
let b = Box(99)
let p2 = Pair(b, "nested")

print(p1.first)
print(p1.second)
print(p2.first.val)
print(p2.second)
