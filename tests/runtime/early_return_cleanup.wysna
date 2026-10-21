fn check_early(flag: bool) -> int {
    let a = [10, 20, 30]
    let s = "allocated_string"
    if flag {
        return len(a) + len(s)
    }
    let b = [40, 50]
    return len(b)
}

fn main() -> unit {
    print("early true:", check_early(true))
    print("early false:", check_early(false))
}
