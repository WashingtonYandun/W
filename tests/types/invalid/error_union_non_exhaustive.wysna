struct FirstError { message: str }
struct SecondError { message: str }

fn fail() -> int ! FirstError | SecondError {
    return Err(FirstError { message: "first" })
}

fn invalid() -> int {
    let value = fail() else err {
        match err {
            FirstError(first) => 0
        }
    }
    return value
}
