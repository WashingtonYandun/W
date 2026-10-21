struct DomainError { code: int }
struct OtherError { code: int }

fn fail() -> int ! DomainError | OtherError {
    return Err(DomainError { code: 1 })
}

fn invalid() -> int {
    let value = fail() else err {
        match err {
            DomainError(1) => 0,
            OtherError(_) => 1
        }
    }
    return value
}
