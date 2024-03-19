class Error(Exception):
    def __init__(self, error_message: str, details: str) -> None:
        self.error_message = error_message
        self.details = details
        super().__init__(self.error_message)

    def __str__(self) -> str:
        return f"{self.error_message}: {self.details}"