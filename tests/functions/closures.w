fn apply(f: fn(int) -> int, x: int) -> int { return f(x) }
fn make_adder(n: int) -> fn(int) -> int {
    return |x: int| => x + n
}
let add = make_adder(7)
print(apply(add, 3))
let mut xs = [1, 2]
let size: fn() -> int = || => len(xs)
xs.append(3)
print(size(), len(xs))
