from app.services.storage import StorageError as PublicationStorageError


class PublicationError(ValueError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail
