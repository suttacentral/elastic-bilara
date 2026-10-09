class PublicationError(ValueError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PublicationStorageError(OSError):
    """Publication file or lock I/O failed; Git tasks can still retry it."""
