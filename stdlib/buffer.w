extern "C" fn w_host_buffer_new() -> opaque
extern "C" fn w_host_buffer_size(handle: opaque) -> int
extern "C" fn w_host_buffer_get(handle: opaque, index: int) -> int
extern "C" fn w_host_buffer_append(handle: opaque, value: int) -> int
extern "C" fn w_host_close(handle: opaque) -> int

pub struct BufferError { message: str }

# Compact mutable bytes have reference identity. Clone explicitly for a snapshot.
pub class Bytes {
    private handle: opaque
    public fn init() { this.handle = w_host_buffer_new() }
    public fn size() -> int { return w_host_buffer_size(this.handle) }
    public fn get(index: int) -> int ! BufferError {
        let value = w_host_buffer_get(this.handle, index)
        if value < 0 { return Err(BufferError { message: "closed buffer or invalid index" }) }
        return value
    }
    public fn append(value: int) -> unit ! BufferError {
        if w_host_buffer_append(this.handle, value) != 0 {
            return Err(BufferError { message: "closed buffer or byte outside 0..255" })
        }
    }
    public fn close() -> int { return w_host_close(this.handle) }
    # Internal interoperability boundary; retaining the ID does not extend its lifetime.
    public fn borrow() -> opaque { return this.handle }
}

pub fn from_text(text: str) -> Bytes {
    let result = Bytes()
    for codepoint in 0..len(text) {
        for byte in bytes(text[codepoint]) {
            result.append(byte) else error { exit(1) }
        }
    }
    return result
}

pub fn clone(source: Bytes) -> Bytes ! BufferError {
    if source.size() < 0 { return Err(BufferError { message: "closed buffer" }) }
    let result = Bytes()
    for index in 0..source.size() {
        let value = source.get(index) else error { result.close() return Err(error) }
        result.append(value) else error { result.close() return Err(error) }
    }
    return result
}
