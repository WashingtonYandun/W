struct RepeatedError { message: str }

fn invalid() -> int ! RepeatedError | RepeatedError {
    return Err(RepeatedError { message: "duplicate alternative" })
}
