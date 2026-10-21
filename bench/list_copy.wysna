# Benchmark 4: O(1) Copy-on-Write list sharing without mutation

fn read_first_last(xs: list[int]) -> int {
    return xs[0] + xs[len(xs) - 1]
}

fn main() -> unit {
    let mut base: list[int] = [1]
    let mut i = 2
    while i <= 1000 {
        base.append(i)
        i = i + 1
    }
    let mut total = 0
    let mut k = 0
    while k < 5000 {
        let copy = base
        total = total + read_first_last(copy)
        k = k + 1
    }
    print(total)
}
