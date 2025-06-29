# Function that takes a list parameter
func sum_list(numbers: list[int]) -> int {
    total: int = 0
    for i in range(len(numbers)) {
        total = total + numbers[i]
    }
    return total
}

my_numbers: list[int] = [1, 2, 3, 4, 5]
total: int = sum_list(my_numbers)
print("Sum of", my_numbers, "=", total)

# Function that returns a list
func create_range(start: int, end: int) -> list[int] {
    result: list[int] = []
    # Note: We can't modify lists yet, so we'll return a pre-made list
    return [1, 2, 3]
}

new_list: list[int] = create_range(1, 4)
print("Created list:", new_list)

# Function that finds maximum in list
func find_max(numbers: list[int]) -> int {
    if len(numbers) == 0 {
        return 0
    }
    
    max_val: int = numbers[0]
    for i in range(1, len(numbers)) {
        if numbers[i] > max_val {
            max_val = numbers[i]
        }
    }
    return max_val
}

test_numbers: list[int] = [3, 7, 2, 9, 1, 5]
max_value: int = find_max(test_numbers)
print("Maximum in", test_numbers, "=", max_value)
