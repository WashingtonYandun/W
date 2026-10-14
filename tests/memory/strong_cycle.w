class Node {
    public next: Node?
    public fn init() -> unit {
        this.next = none
    }
}

fn create_cycle() -> unit {
    let first = Node()
    let second = Node()
    first.next = second
    second.next = first
}

create_cycle()
