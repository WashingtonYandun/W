fn increment(value: int) -> int { return value + 1 }
fn wrap(f: fn(int) -> int) -> fn(int) -> int {
    return |value: int| => f(value) * 2
}
let function = wrap(increment)
print(function(4))
struct Callback { invoke: fn(int) -> int }
let callback = Callback { invoke: increment }
print(callback.invoke(10))
