# Recursive generic ADT: Tree[T] without Box[T] wrapper
enum Tree[T] {
    Leaf(T),
    Node(Tree[T], Tree[T])
}

fn sum_tree(t: Tree[int]) -> int {
    match t {
        Tree.Leaf(val) => val,
        Tree.Node(left, right) => sum_tree(left) + sum_tree(right)
    }
}

let my_tree: Tree[int] = Tree.Node(
    Tree.Leaf(10),
    Tree.Node(Tree.Leaf(20), Tree.Leaf(30))
)

let total = sum_tree(my_tree)
print(total)
