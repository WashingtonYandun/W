pub fn join(parts: list[str], separator: str) -> str {
    let mut result = ""
    for index, part in enumerate(parts) {
        if index > 0 { result = result + separator }
        result = result + part
    }
    return result
}
pub fn pad_left(text: str, width: int, fill: str) -> str {
    if len(fill) == 0 { return text }
    let mut result = text
    while len(result) < width { result = fill + result }
    return result
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
