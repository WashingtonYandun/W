fn nested(n: int) -> fn(int) -> fn(int) -> int {
    return |x: int| => |y: int| => n + x + y
}
let layer = nested(10)
let inner = layer(20)
print(inner(30))
let shadowed = 99
let function: fn(int) -> fn(int) -> int = |shadowed: int| => |y: int| => shadowed + y
print(function(3)(4))
