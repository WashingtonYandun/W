# Standard Library

W distributes modules under `std/` imported via canonical paths such as `import "std/text"`.

## Modules Overview

- `std/buffer`: compact mutable byte arrays (`Bytes`) with boundary validation and lifecycle tracking.
  - `buffer.from_text(str) -> Bytes`: create a byte buffer from UTF-8 string data.
  - `buffer.clone(Bytes) -> Bytes ! BufferError`: clone buffer with isolated storage.
  - `buffer.append(Bytes, int) -> unit ! BufferError`: append a byte (0–255).
  - `buffer.get(Bytes, int) -> int ! BufferError`: access byte by index.
  - `buffer.size(Bytes) -> int`: get buffer length in bytes.
  - `buffer.close(Bytes) -> unit ! BufferError`: release buffer memory explicitly.
- `std/files`: structured block and stream I/O operations returning `FileError`.
  - `files.open(path, mode) -> FileHandle ! FileError`: open file with mode (`"r"`, `"w"`, `"a"`).
  - `files.read_bytes(FileHandle, max_bytes) -> Bytes ! FileError`: read up to `max_bytes`.
  - `files.write_bytes(FileHandle, Bytes) -> int ! FileError`: write bytes to file.
  - `files.close(FileHandle) -> unit ! FileError`: close handle and release host descriptor.
- `std/fs`: filesystem operations returning `IoError`.
  - `fs.exists(path) -> bool`: check if path exists on the host filesystem.
  - `fs.size(path) -> int ! IoError`: get file size in bytes.
  - `fs.mkdir(path) -> unit ! IoError`: create a directory.
  - `fs.remove(path) -> unit ! IoError`: remove a file.
  - `fs.rename(old_path, new_path) -> unit ! IoError`: rename or move a path.
- `std/parse`: recoverable numeric parsing returning `Result` with `ParseError`.
  - `parse.parse_int(text) -> int ! ParseError`: parse 64-bit signed integer with whitespace trimming, optional sign, and overflow checks.
  - `parse.parse_float(text) -> float ! ParseError`: parse IEEE-754 64-bit float with fractional and exponent support.
- `std/text`: string manipulation and query operations.
  - `text.join(parts, separator) -> str`: join string list with separator.
  - `text.pad_left(text, width, fill) -> str`: pad text on the left with fill character.
  - `text.lines(text) -> list[str]`: split text by LF or CRLF lines.
  - `text.starts_with(text, prefix) -> bool`: check prefix.
  - `text.ends_with(text, suffix) -> bool`: check suffix.
  - `text.find(haystack, needle) -> int`: find substring offset, returning `-1` if absent.
  - `text.split(text, separator) -> list[str]`: split text by delimiter.
  - `text.replace(text, target, replacement) -> str`: replace all occurrences.
  - `text.trim(text) -> str`: trim leading and trailing ASCII whitespace.
- `std/path`: file path utilities.
  - `path.join(base, child) -> str`: join paths with directory separator `/`.
  - `path.basename(path) -> str`: extract filename component.
  - `path.dirname(path) -> str`: extract directory component.
  - `path.ext(path) -> str`: extract file extension (including dot, e.g. `".w"`).
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

`std/resources` exports `Resource`, `ResourceError`, `error(message)` and `scope[T, E]`.
- `Resource(handle, dispose)` wraps an opaque native handle and a disposal callback.
- `borrow()` returns `opaque ! ResourceError` and rejects access after close.
- `close()` provides idempotent destruction.
- `scope(resource, body)` ensures the resource is disposed upon block completion (success or error), returning `(T ! E, close_status)`.
