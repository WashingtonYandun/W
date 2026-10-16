fn classify(value: int) -> int {
    match value {
        1 if false => 9,
        1 if true => 7,
        _ => 0
    }
}
print(classify(1))
