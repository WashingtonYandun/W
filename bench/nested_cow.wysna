# Benchmark 6: Recursive Copy-on-Write across nested lists and structs

struct Grid {
    rows: list[list[int]]
}

fn main() -> unit {
    let g0 = Grid { rows: [[1, 2, 3], [4, 5, 6], [7, 8, 9]] }
    let mut checksum = 0
    let mut i = 0
    while i < 2500 {
        let mut g1 = g0
        g1.rows[1].append(i)
        checksum = checksum + g0.rows[1][0] + len(g0.rows[1]) + g1.rows[1][3]
        i = i + 1
    }
    print(checksum)
}
