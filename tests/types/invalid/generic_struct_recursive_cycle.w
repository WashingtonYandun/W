# ERROR: W2011
struct Node[T] {
    val: T,
    next: Node[T]
}

let n: Node[int] = Node(1, Node(2, 0))
