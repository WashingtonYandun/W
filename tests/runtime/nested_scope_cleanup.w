fn main() -> unit {
    let mut sum = 0
    if true {
        let l1 = [1, 2]
        if true {
            let l2 = [3, 4, 5]
            if true {
                let l3 = [6, 7, 8, 9]
                sum = len(l1) + len(l2) + len(l3)
            }
        }
    }
    print("nested sum:", sum)
}
