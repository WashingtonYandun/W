import "std/buffer"
extern "C" fn w_host_file_open(path: opaque, mode: int) -> opaque
extern "C" fn w_host_file_read(file: opaque, data: opaque, count: int) -> int
extern "C" fn w_host_file_write(file: opaque, data: opaque) -> int
extern "C" fn w_host_is_open(file: opaque) -> int
extern "C" fn w_host_close(handle: opaque) -> int
extern "C" fn w_host_last_error() -> int
extern "C" fn w_host_last_error_domain() -> int

pub struct FileError { operation: str, path: str, code: int, domain: int }

pub class File {
    private handle: opaque
    private path: str
    public fn init(path: str, mode: int) {
        let encoded = buffer.from_text(path)
        this.handle = w_host_file_open(encoded.borrow(), mode)
        encoded.close()
        this.path = path
    }
    public fn is_open() -> bool { return w_host_is_open(this.handle) == 1 }
    public fn read(count: int) -> buffer.Bytes ! FileError {
        let data = new buffer.Bytes()
        if w_host_file_read(this.handle, data.borrow(), count) < 0 {
            let code = w_host_last_error()
            let domain = w_host_last_error_domain()
            data.close()
            return Err(FileError { operation: "read", path: this.path, code: code, domain: domain })
        }
        return data
    }
    public fn write(data: buffer.Bytes) -> unit ! FileError {
        if w_host_file_write(this.handle, data.borrow()) != 0 {
            return Err(FileError { operation: "write", path: this.path, code: w_host_last_error(), domain: w_host_last_error_domain() })
        }
    }
    public fn close() -> int { return w_host_close(this.handle) }
}

# Modes: 0 read, 1 truncate/write, 2 append. EOF is an empty Bytes buffer.
pub fn open(path: str, mode: int) -> File ! FileError {
    let file = File(path, mode)
    if not file.is_open() { return Err(FileError { operation: "open", path: path, code: w_host_last_error(), domain: w_host_last_error_domain() }) }
    return file
}

pub fn scope[T, E](file: File, body: fn(File) -> T ! E) -> tuple[T ! E, int] {
    let result: T ! E = body(file)
    let status = file.close()
    return (result, status)
}
