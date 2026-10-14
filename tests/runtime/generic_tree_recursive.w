struct Box[T] {
    val: T
}

enum Tree[T] {
    Leaf(T),
    Node(Box[Tree[T]], Box[Tree[T]])
}

fn sum_tree(t: Tree[int]) -> int {
    return match t {
        Leaf(v) => v,
        Node(l, r) => sum_tree(l.val) + sum_tree(r.val)
    }
}

let left = Tree.Leaf(10)
let right = Tree.Leaf(20)
let root = Tree.Node(Box(left), Box(right))

print("Tree sum:", sum_tree(root))
