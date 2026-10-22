pub struct ParseError { offset: int, message: str }
fn space(value: str) -> bool { return value == " " or value == "\t" or value == "\n" or value == "\r" or value == "\u{b}" or value == "\u{c}" }
fn start_offset(text: str) -> int {
    let mut start = 0
    while start < len(text) and space(text[start]) { start = start + 1 }
    return start
}
fn end_offset(text: str) -> int {
    let mut end = len(text)
    while end > 0 and space(text[end - 1]) { end = end - 1 }
    return end
}
fn digit(text: str) -> bool { let value = ord(text) return value >= 48 and value <= 57 }
pub fn parse_int(text: str) -> int ! ParseError {
    let start = start_offset(text)
    let end = end_offset(text)
    let mut index = start
    let mut negative = false
    if index < end and (text[index] == "-" or text[index] == "+") { negative = text[index] == "-" index = index + 1 }
    if index == end { return Err(ParseError { offset: index, message: "expected integer" }) }
    let limit = if negative { -9223372036854775808 } else { -9223372036854775807 }
    let mut value = 0
    while index < end {
        if not digit(text[index]) { return Err(ParseError { offset: index, message: "expected ASCII digit" }) }
        let next = ord(text[index]) - 48
        if value < limit / 10 { return Err(ParseError { offset: index, message: "integer overflow" }) }
        value = value * 10
        if value < limit + next { return Err(ParseError { offset: index, message: "integer overflow" }) }
        value = value - next
        index = index + 1
    }
    return if negative { value } else { -value }
}
pub fn parse_float(text: str) -> float ! ParseError {
    let start = start_offset(text)
    let end = end_offset(text)
    let mut index = start
    if index < end and (text[index] == "-" or text[index] == "+") { index = index + 1 }
    let mut digits = 0
    while index < end and digit(text[index]) { digits = digits + 1 index = index + 1 }
    if index < end and text[index] == "." {
        index = index + 1
        while index < end and digit(text[index]) { digits = digits + 1 index = index + 1 }
    }
    if digits == 0 { return Err(ParseError { offset: index, message: "expected decimal" }) }
    if index < end and (text[index] == "e" or text[index] == "E") {
        index = index + 1
        if index < end and (text[index] == "-" or text[index] == "+") { index = index + 1 }
        let exponent = index
        while index < end and digit(text[index]) { index = index + 1 }
        if index == exponent { return Err(ParseError { offset: index, message: "expected exponent" }) }
    }
    if index != end { return Err(ParseError { offset: index, message: "unexpected character" }) }
    let value = float(slice(text, start, end))
    if value != value or str(value) == "inf" or str(value) == "-inf" { return Err(ParseError { offset: start, message: "float overflow" }) }
    return value
}
