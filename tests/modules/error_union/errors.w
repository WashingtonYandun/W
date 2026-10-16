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
