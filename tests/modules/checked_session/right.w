import "shared.w"

pub struct Item {
    value: str,
}

pub fn make() -> Item {
    return Item { value: "right" }
}
