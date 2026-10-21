# Benchmark 2: Function call dispatch and evaluation order

fn step(a: int, b: int) -> int {
    return a * 2 + b - 1
}

fn combine(x: int) -> int {
    return step(x, x + 1) + step(x + 2, x + 3)
}

fn main() -> unit {
    let mut total = 0
    let mut i = 0
    while i < 8000 {
        total = (total + combine(i)) % 1000000
        i = i + 1
    }
    print(total)
}
