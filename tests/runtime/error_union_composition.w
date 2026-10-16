struct ParseError {
    message: str
}

enum FileError {
    Missing
}

fn parse_value() -> int ! ParseError {
    return Err(ParseError { message: "parse failed" })
}

fn load_value() -> int ! int {
    return Err(17)
}

fn read_missing() -> int ! FileError {
    return Err(FileError.Missing)
}

fn parse_or_file(route: int) -> int ! ParseError | FileError {
    if route == 0 {
        return parse_value()?
    }
    return read_missing()?
}

fn combined(route: int) -> int ! ParseError | FileError | int {
    if route == 2 {
        return load_value()?
    }
    return parse_or_file(route)?
}

fn report(route: int) -> int {
    return combined(route) else err {
        match err {
            ParseError(parse_error) => {
                print(parse_error.message)
                0
            },
            FileError(file_error) => {
                print(file_error)
                0
            },
            int(code) => {
                print(code)
                0
            }
        }
    }
}

print(report(0), report(1), report(2))
