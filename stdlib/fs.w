import "std/buffer"
extern "C" fn w_host_fs(first: opaque, second: opaque, operation: int) -> int
pub struct FsError { operation: str, path: str, code: int }

fn apply(path: str, target: str, operation: int, name: str) -> int ! FsError {
    let first = buffer.from_text(path)
    let second = buffer.from_text(target)
    let status = w_host_fs(first.borrow(), second.borrow(), operation)
    first.close()
    second.close()
    if status < 0 { return Err(FsError { operation: name, path: path, code: status }) }
    return status
}
pub fn exists(path: str) -> bool ! FsError { return apply(path, "", 0, "exists")? == 1 }
pub fn size(path: str) -> int ! FsError { return apply(path, "", 1, "size") }
pub fn mkdir(path: str) -> unit ! FsError { let status = apply(path, "", 2, "mkdir")? }
pub fn remove(path: str) -> unit ! FsError { let status = apply(path, "", 3, "remove")? }
pub fn rename(path: str, target: str) -> unit ! FsError { let status = apply(path, target, 4, "rename")? }
