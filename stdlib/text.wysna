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

pub fn starts_with(text: str, prefix: str) -> bool {
    return len(prefix) <= len(text) and slice(text, 0, len(prefix)) == prefix
}
pub fn ends_with(text: str, suffix: str) -> bool {
    return len(suffix) <= len(text) and slice(text, len(text) - len(suffix), len(text)) == suffix
}
pub fn find(text: str, pattern: str) -> int? {
    if len(pattern) > len(text) { return none }
    for index in 0..=len(text) - len(pattern) {
        if slice(text, index, index + len(pattern)) == pattern { return index }
    }
    return none
}
pub fn split(text: str, separator: str) -> list[str] {
    let mut result: list[str] = []
    if len(separator) == 0 {
        for index in 0..len(text) { result.append(text[index]) }
        return result
    }
    let mut start = 0
    let mut index = 0
    while index + len(separator) <= len(text) {
        if slice(text, index, index + len(separator)) == separator {
            result.append(slice(text, start, index))
            index = index + len(separator)
            start = index
        } else { index = index + 1 }
    }
    result.append(slice(text, start, len(text)))
    return result
}
pub fn replace(text: str, pattern: str, replacement: str) -> str {
    if len(pattern) == 0 { return text }
    return join_strings(split(text, pattern), replacement)
}
pub fn trim(text: str) -> str {
    let mut start = 0
    let mut end = len(text)
    while start < end and ord(text[start]) <= 32 and (text[start] == " " or ord(text[start]) >= 9 and ord(text[start]) <= 13) { start = start + 1 }
    while end > start and ord(text[end - 1]) <= 32 and (text[end - 1] == " " or ord(text[end - 1]) >= 9 and ord(text[end - 1]) <= 13) { end = end - 1 }
    return slice(text, start, end)
}
