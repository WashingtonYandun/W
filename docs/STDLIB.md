# Standard Library

W0 distributes these modules under `std/` and imports them with paths such as `std/text`.

- `std/io`: `read_text(path)` and `write_text(path, content)` return the `IoError` error channel. Text must be valid UTF-8; NUL bytes are preserved.
- `std/text`: `join(parts, separator)`, `pad_left(text, width, fill)`, and `lines(text)`. Widths count Unicode scalar values, not display columns or grapheme clusters. `lines` accepts LF and CRLF and omits a final empty line. A multi-character fill may exceed the requested width.
- `std/algorithms`: `map[T,R]`, `fold[T,R]`, and `sort[T]`. Sorting is stable, uses merge sort, requires a strict comparator, returns an independent list, takes O(n log n) time, and uses O(n) auxiliary memory. It does not mutate the input.
- `std/bytes`: `encode(text)` and `decode(bytes)`. The decoder rejects out-of-range bytes, truncated sequences, invalid continuations, overlong encodings, surrogate values, and code points above U+10FFFF. `Utf8Error.offset` identifies the failing byte.

The library is intentionally small. Repeated string concatenation copies content; `join`, `pad_left`, and `decode` are not streaming operations for large data. Networking, binary streams, locales, and Unicode normalization are not provided.
