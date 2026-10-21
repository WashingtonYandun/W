struct FirstError { message: str }
struct SecondError { message: str }

fn first() -> int ! FirstError {
    return Err(FirstError { message: "first" })
}

fn invalid() -> int ! SecondError {
    return first()?
}
