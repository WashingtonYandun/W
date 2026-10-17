class Node {
    public next: Node?
    fn init() { this.next = none }
}
fn exercise() -> unit {
    let node = Node()
    node.next = node
    print(node)
    print(str(node))
    print([node], (node, node))
    node.next = none
    print([node, node])
    let other = Node()
    node.next = other
    other.next = node
    print(node)
    node.next = none
    other.next = none
}
exercise()
