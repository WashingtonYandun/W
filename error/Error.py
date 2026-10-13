class WError(Exception):
    """
    Base diagnostic exception for W Language toolchain.
    
    Attributes:
        message (str): Explanatory error message.
        line (int): 1-based source line.
        col (int): 1-based source column.
        file (str): Source filename or identifier.
        code (str): Diagnostic code (e.g. 'E001').
    """
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E000") -> None:
        self.message = message
        self.line = line
        self.col = col
        self.file = file
        self.code = code
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return f"[{self.code}] {self.file}:{self.line}:{self.col} - {self.message}"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "file": self.file,
            "line": self.line,
            "column": self.col,
            "message": self.message,
        }


class LexerError(WError):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E001") -> None:
        super().__init__(message=message, line=line, col=col, file=file, code=code)


class ParserError(WError):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E100") -> None:
        super().__init__(message=message, line=line, col=col, file=file, code=code)


class TypeError(WError):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E200") -> None:
        super().__init__(message=message, line=line, col=col, file=file, code=code)


class EnvironmentError(WError):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E300") -> None:
        super().__init__(message=message, line=line, col=col, file=file, code=code)


class WRuntimeError(WError):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = "<stdin>", code: str = "E400") -> None:
        super().__init__(message=message, line=line, col=col, file=file, code=code)


# Backward compatibility aliases
Error = WError
RuntimeError = WRuntimeError