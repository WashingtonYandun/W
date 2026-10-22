struct Container {
    items: list[int]
    label: str
}

fn main() -> unit {
    let c1 = Container { items: [1, 2, 3], label: "orig" }
    let mut c2 = c1
    if true {
        c2.items.append(4)
        c2.label = "modified"
    }
    print("c1:", len(c1.items), c1.label)
    print("c2:", len(c2.items), c2.label)
}
