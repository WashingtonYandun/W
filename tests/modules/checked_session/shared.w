print("init")

struct Item {
    value: bool,
}

enum Mode { On, Off }

fn mode() -> Mode {
    return On
}

fn shadow(value: int) -> int {
    return value
}

fn identity[Item](x: Item) -> Item {
    return x
}

fn id[T](x: T) -> T {
    return x
}

let values = [3]

fn value() -> int {
    return id(values[0])
}

fn main() -> unit {
    print("imported entry must not run")
}
