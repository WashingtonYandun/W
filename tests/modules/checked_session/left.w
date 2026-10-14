import "shared.w"

struct Item {
    value: int,
}

fn make() -> Item {
    return Item { value: shared.value() }
}
