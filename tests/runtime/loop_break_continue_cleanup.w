fn test_loop_cleanup() -> int {
    let mut count = 0
    let mut i = 0
    while i < 10 {
        let chunk = [i, i * 2]
        if i == 3 {
            i = i + 1
            continue
        }
        if i == 7 {
            break
        }
        count = count + chunk[0] + chunk[1]
        i = i + 1
    }
    return count
}

fn main() -> unit {
    print("loop cleanup count:", test_loop_cleanup())
}
