class Error(Exception):
    """
    Represents an error that occurred during the execution of a program.

    Attributes:
        error_message (str): A brief description of the error.
        details (str): Additional details about the error.
    """

    def __init__(self, error_message: str, details: str) -> None:
        self.error_message = error_message
        self.details = details
        super().__init__(self.error_message)

    def __str__(self) -> str:
        return f"{self.error_message}: {self.details}"

class LexerError(Error):
    def __init__(self, details: str) -> None:
        super().__init__("Lexer Error", details)


class ParserError(Error):
    def __init__(self, details: str) -> None:
        super().__init__("Parser Error", details)


class EnvironmentError(Error):
    def __init__(self, details: str) -> None:
        super().__init__("Environment Error", details)