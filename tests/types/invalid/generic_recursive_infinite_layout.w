# ERROR: W2011
struct CycleA[T] {
    val: T,
    b: CycleB[T]
}

struct CycleB[T] {
    val: T,
    a: CycleA[T]
}

let a: CycleA[int] = CycleA(1, CycleB(2, a))
