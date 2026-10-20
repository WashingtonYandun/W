# Standard Library

W0 distributes these modules under `std/` and imports them with paths such as `std/text`.

- `std/io`: `read_text(path)` and `write_text(path, content)` return the `IoError` error channel. Text must be valid UTF-8; NUL bytes are preserved.
- `std/text`: `join(parts, separator)`, `pad_left(text, width, fill)`, and `lines(text)`. Widths count Unicode scalar values, not display columns or grapheme clusters. `lines` accepts LF and CRLF and omits a final empty line. A multi-character fill may exceed the requested width.
- `std/algorithms`: `map[T,R]`, `fold[T,R]`, and `sort[T]`. Sorting is stable, uses merge sort, requires a strict comparator, returns an independent list, takes O(n log n) time, and uses O(n) auxiliary memory. It does not mutate the input.
- `std/bytes`: `encode(text)` and `decode(bytes)`. The decoder rejects out-of-range bytes, truncated sequences, invalid continuations, overlong encodings, surrogate values, and code points above U+10FFFF. `Utf8Error.offset` identifies the failing byte.

The library is intentionally small. Repeated string concatenation copies content; `join`, `pad_left`, and `decode` are not streaming operations for large data. Networking, binary streams, locales, and Unicode normalization are not provided.

## External resources

`std/resources` exports `Resource`, `ResourceError`, `error(message)` and `scope[T,E]`.
`Resource(handle, dispose)` takes an opaque handle and a `fn(opaque) -> int` callback:
0 means closed, while nonzero means the handle remains valid and closing can be retried.
`borrow()` returns `opaque ! ResourceError` and rejects borrowing after successful close.
`close()` is idempotent through this owner.

`scope(resource, body)` invokes the callback, then closes after success or Err, returning
`(T ! E, close_status)` so neither outcome is hidden. The caller must inspect both.
Callbacks must not free the handle by another path or use escaped aliases after close.
Scopes do not intercept panic/exit, collect ARC cycles, or provide linear types.
