print("init")

pub struct Item {
    value: bool,
}

pub enum Mode { On, Off }

pub fn mode() -> Mode {
    return On
}

pub fn shadow(value: int) -> int {
    return value
}

pub fn identity[Item](x: Item) -> Item {
    return x
}

pub fn id[T](x: T) -> T {
    return x
}

pub let values = [3]

pub fn value() -> int {
    return id(values[0])
}

pub fn main() -> unit {
    print("imported entry must not run")
}
