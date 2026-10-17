pub struct ResourceError { message: str }

pub fn error(message: str) -> ResourceError {
    return ResourceError { message: message }
}

pub class Resource {
    private handle: opaque
    private dispose: fn(opaque) -> int
    private closed: bool

    public fn init(handle: opaque, dispose: fn(opaque) -> int) {
        this.handle = handle
        this.dispose = dispose
        this.closed = false
    }

    public fn borrow() -> opaque ! ResourceError {
        if this.closed { return Err(ResourceError { message: "resource is closed" }) }
        return this.handle
    }

    public fn close() -> int {
        if this.closed { return 0 }
        let status = this.dispose(this.handle)
        if status == 0 { this.closed = true }
        return status
    }
}

pub fn scope[T, E](resource: Resource, body: fn(Resource) -> T ! E) -> tuple[T ! E, int] {
    let result: T ! E = body(resource)
    let close_status = resource.close()
    return (result, close_status)
}
