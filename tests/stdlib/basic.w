import "std/algorithms" as algorithms
import "std/text" as text
import "std/bytes" as utf8
let original = [3, 1, 2, 1]
let ordered = algorithms.sort(original, |a: int, b: int| => a < b)
let doubled = algorithms.map(ordered, |value: int| => value * 2)
print(original, ordered, doubled)
print(text.join(["uno", "dos"], ", "), text.lines("a\r\nb\n"))
let decoded = utf8.decode(utf8.encode("á\0😀")) else err { "invalid" }
print(len(decoded), len(utf8.encode(decoded)))
