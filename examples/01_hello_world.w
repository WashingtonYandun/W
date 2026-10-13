## 01_hello_world.w
## Basic functions, type annotations, ranges, and loops in W v0.1.

fn greet(name: str) -> str {
    return "Hello, " + name + "! Welcome to W v0.1."
}

fn sum_range(limit: int) -> int {
    let mut total = 0
    for i in 1..=limit {
        total = total + i
    }
    return total
}

fn main() -> unit {
    print(greet("Washo"))
    print("Sum 1..=10:", sum_range(10))
    print("Sum 1..=100:", sum_range(100))
}
