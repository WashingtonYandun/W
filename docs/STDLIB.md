# Standard Library

W distributes modules under `std/` imported via canonical paths such as `import "std/text"`.

## Modules Overview

- `std/buffer`: compact mutable byte arrays (`Bytes`) with boundary validation and lifecycle tracking.
  - `buffer.from_text(str) -> Bytes`: create a byte buffer from UTF-8 string data.
  - `buffer.clone(Bytes) -> Bytes ! BufferError`: clone buffer with isolated storage.
  - `Bytes.append(int) -> unit ! BufferError`: append a byte (0–255).
  - `Bytes.get(int) -> int ! BufferError`: access byte by index.
  - `Bytes.size() -> int`: get buffer length in bytes.
  - `Bytes.close() -> int`: release buffer memory explicitly.
- `std/files`: structured block and stream I/O operations returning `FileError`.
  - `files.open(path, mode) -> File ! FileError`: open file with integer mode (`0` read, `1` truncate/write, `2` append).
  - `File.read(max_bytes) -> Bytes ! FileError`: read up to `max_bytes`.
  - `File.write(Bytes) -> unit ! FileError`: write bytes to file.
  - `File.close() -> int`: close handle and release host descriptor.
- `std/fs`: filesystem operations returning `FsError`.
  - `fs.exists(path) -> bool ! FsError`: check if path exists on the host filesystem.
  - `fs.size(path) -> int ! FsError`: get file size in bytes.
  - `fs.mkdir(path) -> unit ! FsError`: create a directory.
  - `fs.remove(path) -> unit ! FsError`: remove a file.
  - `fs.rename(old_path, new_path) -> unit ! FsError`: rename or move a path.
- `std/parse`: recoverable numeric parsing returning `Result` with `ParseError`.
  - `parse.parse_int(text) -> int ! ParseError`: parse 64-bit signed integer with whitespace trimming, optional sign, and overflow checks.
  - `parse.parse_float(text) -> float ! ParseError`: parse IEEE-754 64-bit float with fractional and exponent support.
- `std/text`: string manipulation and query operations.
  - `text.join(parts, separator) -> str`: join string list with separator.
  - `text.pad_left(text, width, fill) -> str`: pad text on the left with fill character.
  - `text.lines(text) -> list[str]`: split text by LF or CRLF lines.
  - `text.starts_with(text, prefix) -> bool`: check prefix.
  - `text.ends_with(text, suffix) -> bool`: check suffix.
  - `text.find(haystack, needle) -> int?`: find codepoint offset, returning `none` if absent.
  - `text.split(text, separator) -> list[str]`: split text by delimiter.
  - `text.replace(text, target, replacement) -> str`: replace all occurrences.
  - `text.trim(text) -> str`: trim leading and trailing ASCII whitespace.
- `std/path`: file path utilities.
  - `path.join(base, child) -> str`: join paths with directory separator `/`.
  - `path.basename(path) -> str`: extract filename component.
  - `path.dirname(path) -> str`: extract directory component.
- `std/io`: text file convenience wrappers.
  - `io.read_text(path) -> str ! IoError`: read full UTF-8 file to string.
  - `io.write_text(path, content) -> unit ! IoError`: write full string to file.
- `std/algorithms`: functional collection algorithms.
  - `algorithms.map[T, R]` `(values, fn(T) -> R) -> list[R]`: transform list elements.
  - `algorithms.fold[T, R]` `(values, initial, fn(R, T) -> R) -> R`: fold accumulator over list.
  - `algorithms.sort[T]` `(values, fn(T, T) -> bool) -> list[T]`: stable merge sort with $O(N \log N)$ complexity.
- `std/bytes`: UTF-8 codec operations.
  - `bytes.encode(text) -> list[int]`: encode UTF-8 string into byte values (0–255).
  - `bytes.decode(bytes) -> str ! Utf8Error`: decode byte values into validated UTF-8 string.

## External Resources & Scopes

`std/resources` exports `Resource`, `ResourceError`, `error(message)`, `acquire(handle, dispose)` and `scope[T, E]`.
- `acquire(handle, dispose) -> Resource ! ResourceError` claims an opaque native handle and a disposal callback; duplicate ownership is rejected.
- `borrow()` returns `opaque ! ResourceError` and rejects access after close.
- `close()` provides idempotent destruction.
- `scope(resource, body)` ensures the resource is disposed upon block completion (success or error), returning `(T ! E, close_status)`.

## Standard resource lifetime and errors

`Bytes` and `File` retain trusted host owners. Aliases share identity; losing the last
owner closes the host entry automatically. `Bytes.borrow()` returns a checked,
non-owning ID and does not prolong lifetime. A stale ID fails validation. Explicit
`close() -> int` consumes the host entry once, returns 0 on success and -1 on IO
failure; repeated close returns 0. Closing one alias closes all aliases. A fallback
close at last release is best effort; call close explicitly to observe flush errors.
No arbitrary W finalizer runs during release. Strong ARC cycles are not collected.
Raw FFI `opaque` pointers and `resources.Resource` disposal callbacks still require
explicit close or `resources.scope`; they do not acquire automatic user finalizers.
Scope helpers close after success or a returned error; panic/exit/cancellation is
not a language-level unwinding guarantee.

`FileError` and `FsError` have `operation: str`, `path: str`, `code: int`, and
`domain: int`. Failure codes are positive platform codes: domain 1 is errno,
domain 2 is Win32. Capture occurs before cleanup. File.read accepts 1..16777216
bytes; EOF returns an empty owned Bytes. A closed handle and an invalid read bound
return recoverable errors. File.write checks both short writes and fflush failures;
flush does not guarantee durable storage. Rename replaces a destination according
to host rules and rejects cross-volume copy fallback; it is not a durability promise.

The internal diagnostic ABI exposes `wysna_host_active_handles()` and
`wysna_host_active_bytes()` for persistent workload tests. Handles include buffers,
files and raw resource claims. Bytes measure reserved buffer capacity in C and
payload bytes in the reference engine; neither metric is process RSS.
