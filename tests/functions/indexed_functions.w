fn increment(value: int) -> int { return value + 1 }
let callbacks = [increment]
let index = 0
print(callbacks[index](41))
let table = {"step": increment}
let step = table["step"] ?? increment
print(step(10))
