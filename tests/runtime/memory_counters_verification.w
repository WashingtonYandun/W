fn churn_memory(iterations: int) -> int {
    let mut acc = 0
    let mut i = 0
    while i < iterations {
        let temp_list = [i, i + 1, i + 2]
        let temp_dict = {"k": i}
        let temp_str = "churn_" + str(i)
        acc = acc + len(temp_list) + len(temp_dict) + len(temp_str)
        i = i + 1
    }
    return acc
}

fn main() -> unit {
    let total = churn_memory(100)
    print("memory churn ok:", total > 0)
}
