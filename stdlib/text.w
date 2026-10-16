pub fn join(parts: list[str], separator: str) -> str {
    return join_strings(parts, separator)
}
pub fn pad_left(text: str, width: int, fill: str) -> str {
    let size = len(fill)
    let length = len(text)
    if size == 0 or width <= length { return text }
    let missing = width - length
    let copies = missing / size + if missing % size != 0 { 1 } else { 0 }
    let mut parts: list[str] = []
    for index in 0..copies { parts.append(fill) }
    parts.append(text)
    return join_strings(parts, "")
}
pub fn lines(text: str) -> list[str] {
    let mut result: list[str] = []
    let mut start = 0
    for index in 0..len(text) {
        if text[index] == "\n" {
            let mut end = index
            if end > start and text[end - 1] == "\r" { end = end - 1 }
            result.append(slice(text, start, end))
            start = index + 1
        }
    }
    if start < len(text) { result.append(slice(text, start, len(text))) }
    return result
}
