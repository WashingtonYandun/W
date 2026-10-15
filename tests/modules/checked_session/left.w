pub import "shared.w"

pub struct Item {
    value: int,
}

pub fn make() -> Item {
    return Item { value: shared.value() }
}
