"""API error type and the `{error: {code, message}}` response shape (internal details stay in the logs)."""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ImportFailure(Exception):
    """An import problem whose message is safe to show the user (stored in repositories.error_message)."""
