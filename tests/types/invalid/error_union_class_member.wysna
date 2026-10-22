class ClassError {}
struct DomainError { message: str }

fn invalid() -> int ! ClassError | DomainError {
    return Err(DomainError { message: "unsupported alternative" })
}
