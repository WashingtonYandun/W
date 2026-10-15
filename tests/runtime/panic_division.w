# A runtime panic must be reported identically by every engine and must terminate the
# process with a non-zero status. Without fixtures like this the four engines could
# diverge on panic behaviour -- which is exactly what they did -- and no test noticed.
fn divide(a: int, b: int) -> int {
    return a / b
}

fn main() {
    let mut zero = 0
    print(divide(10, zero))
}

main()
