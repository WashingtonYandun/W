import "std/buffer"
import "std/parse"
import "std/text"
fn main() -> unit ! parse.ParseError | buffer.BufferError {
    print(parse.parse_int(" -9223372036854775808 ")?, parse.parse_int("+9223372036854775807")?)
    for invalid in ["", "+", "9223372036854775808", "-9223372036854775809", "12x", "１２"] {
        parse.parse_int(invalid) else error { print("invalid integer", error.offset) continue }
    }
    print(parse.parse_float(" 1.25e2 ")?, parse.parse_float("-.5")?)
    for invalid in ["", "1e", ".", "nan", "1e9999", "1\0"] {
        parse.parse_float(invalid) else error { print("invalid float", error.offset) continue }
    }
    print(text.split("a::b::", "::"), text.split("éx", ""))
    print(text.trim(" x\r\n"), text.replace("ab-ab", "ab", "é"))
    print(text.starts_with("hello", "he"), text.ends_with("hello", "lo"), text.find("hello", "ll"))
    let data = buffer.from_text("a\0é")
    let copy = buffer.clone(data)?
    data.append(255)?
    print(data.size(), copy.size(), copy.get(1)?, data.get(4)?)
    print(data.close(), data.close())
    data.get(0) else error { print(error.message)
        0 }
    data.append(1) else error { print(error.message) }
    print(copy.close())
}
