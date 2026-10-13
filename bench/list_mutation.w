# Benchmark 5: Copy-on-Write detachment on list mutation

fn main() -> unit {
    let base = [10, 20, 30, 40, 50, 60, 70, 80]
    let mut total = 0
    let mut i = 0
    while i < 4000 {
        let mut branch = base
        branch[0] = i
        branch.append(i + 1)
        total = total + branch[0] + branch[len(branch) - 1] + base[0]
        i = i + 1
    }
    print(total)
}
