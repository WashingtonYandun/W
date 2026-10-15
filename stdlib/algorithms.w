pub fn map[T, R](values: list[T], transform: fn(T) -> R) -> list[R] {
    let mut result: list[R] = []
    for value in values { result.append(transform(value)) }
    return result
}
pub fn fold[T, R](values: list[T], initial: R, combine: fn(R, T) -> R) -> R {
    let mut result = initial
    for value in values { result = combine(result, value) }
    return result
}
pub fn sort[T](values: list[T], before: fn(T, T) -> bool) -> list[T] {
    if len(values) < 2 { return values }
    let middle = len(values) / 2
    let mut left: list[T] = []
    let mut right: list[T] = []
    for index in 0..len(values) {
        if index < middle { left.append(values[index]) }
        else { right.append(values[index]) }
    }
    left = sort[T](left, before)
    right = sort[T](right, before)
    let mut result: list[T] = []
    let mut i = 0
    let mut j = 0
    while i < len(left) and j < len(right) {
        if before(right[j], left[i]) { result.append(right[j]) j = j + 1 }
        else { result.append(left[i]) i = i + 1 }
    }
    while i < len(left) { result.append(left[i]) i = i + 1 }
    while j < len(right) { result.append(right[j]) j = j + 1 }
    return result
}
