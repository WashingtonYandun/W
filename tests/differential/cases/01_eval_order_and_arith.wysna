# Differential Case 01: Arithmetic, Precedence, Recursion & Control Flow

fn fib(n: int) -> int {
    if n <= 1 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

fn step_val(log: list[int], tag: int, val: int) -> int {
    print("eval:", tag, val)
    return val
}

fn combine3(a: int, b: int, c: int) -> int {
    return a * 100 + b * 10 + c
}

fn main() -> unit {
    let dummy: list[int] = [0]
    let r1 = combine3(
        step_val(dummy, 1, 3),
        step_val(dummy, 2, 7),
        step_val(dummy, 3, 9)
    )
    print("combine3:", r1)

    let r2 = step_val(dummy, 10, 4) + step_val(dummy, 20, 5) * step_val(dummy, 30, 6)
    print("arith_order:", r2)

    let mut acc = 0
    for i in 1..=8 {
        acc = acc + fib(i)
    }
    print("fib_sum:", acc)
}
