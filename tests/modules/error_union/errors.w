pub struct ParseError {
    message: str
}

pub enum FileError {
    Missing
}

pub fn parse_error() -> ParseError {
    return ParseError { message: "parse failed" }
}

pub fn file_error() -> FileError {
    return FileError.Missing
}

pub fn local_failure() -> int ! ParseError | FileError {
    return Err(parse_error())
}

pub fn recover_local() -> int {
    return local_failure() else err {
        match err {
            ParseError(error) => len(error.message),
            FileError(_) => 0
        }
    }
}
