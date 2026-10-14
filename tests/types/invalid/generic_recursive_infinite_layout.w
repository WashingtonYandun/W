# ERROR: W2011
enum BadTree[T] {
    Leaf(T),
    Node(BadTree[T], BadTree[T])
}

let t: BadTree[int] = BadTree.Leaf(1)
