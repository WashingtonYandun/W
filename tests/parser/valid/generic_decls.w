struct Box[T] {
    val: T
}

struct Pair[A, B] {
    a: A,
    b: B
}

fn id[T](x: T) -> T {
    return x
}

fn process[T: Printable, R](item: T) -> R {
    return item
}
