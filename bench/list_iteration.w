# Benchmark 3: List construction and iteration

fn main() -> unit {
    let mut items: list[int] = [0]
    let mut i = 1
    while i < 2000 {
        items.append(i)
        i = i + 1
    }
    let mut sum = 0
    let mut round = 0
    while round < 10 {
        for x in items {
            sum = sum + x
        }
        round = round + 1
    }
    print(sum)
}
