const target: int = 3
arr: list[int] = [1, 2, 3, 4, 5]

func two_sum(target: int, arr: list[int]) -> list[int] {
    for i in range(len(arr)){
        for j in range(i + 1, len(arr)){
            if arr[i] + arr[j] == target {
                return [arr[i], arr[j]]
            }
        }
    }
    return []
}

print(two_sum(target, arr))