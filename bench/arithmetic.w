# Benchmark 1: 64-bit integer arithmetic & control flow loop

fn main() -> unit {
    let mut acc = 0
    let mut i = 1
    while i <= 15000 {
        acc = (acc + i * 3 - (i / 2)) % 1000007
        i = i + 1
    }
    print(acc)
}
