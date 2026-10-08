"""Expected application errors, independent of HTTP frameworks."""


class AppError(Exception):
    """Carry a safe message and a stable error code to the HTTP boundary."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
