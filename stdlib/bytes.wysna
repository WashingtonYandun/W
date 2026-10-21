pub struct Utf8Error { offset: int }
pub fn encode(text: str) -> list[int] { return bytes(text) }
pub fn decode(data: list[int]) -> str ! Utf8Error {
    let mut parts: list[str] = []
    let mut index = 0
    while index < len(data) {
        let first = data[index]
        let mut count = 1
        let mut codepoint = first
        let mut minimum = 0
        if first < 0 or first > 244 { return Err(Utf8Error { offset: index }) }
        if first >= 240 { count = 4 codepoint = first - 240 minimum = 65536 }
        elif first >= 224 { count = 3 codepoint = first - 224 minimum = 2048 }
        elif first >= 194 { count = 2 codepoint = first - 192 minimum = 128 }
        elif first >= 128 { return Err(Utf8Error { offset: index }) }
        if index + count > len(data) { return Err(Utf8Error { offset: index }) }
        for offset in 1..count {
            let next = data[index + offset]
            if next < 128 or next > 191 { return Err(Utf8Error { offset: index + offset }) }
            codepoint = codepoint * 64 + next - 128
        }
        if codepoint < minimum or codepoint > 1114111 or (codepoint >= 55296 and codepoint <= 57343) {
            return Err(Utf8Error { offset: index })
        }
        parts.append(chr(codepoint))
        index = index + count
    }
    return join_strings(parts, "")
}
