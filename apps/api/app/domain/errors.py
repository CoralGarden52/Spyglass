from collections.abc import Mapping


class DomainError(Exception):
    def __init__(
        self, status: int, code: str, message: str, headers: Mapping[str, str] | None = None
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers
        super().__init__(code)
