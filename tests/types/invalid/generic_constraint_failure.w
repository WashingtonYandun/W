# ERROR: W2001
interface Printable {
    fn to_string() -> str
}

fn describe[T: Printable](item: T) -> str {
    return "desc"
}

let num = 42
let res = describe(num)
