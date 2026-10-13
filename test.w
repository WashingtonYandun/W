fn two_sum(target: int, arr: list[int]) -> list[int] {
    for i in 0..len(arr) {
        for j in (i + 1)..len(arr) {
            if arr[i] + arr[j] == target {
                return [arr[i], arr[j]]
            }
        }
    }
    let empty: list[int] = []
    return empty
}

let target = 3
let arr = [1, 2, 3, 4, 5]
print(two_sum(target, arr))