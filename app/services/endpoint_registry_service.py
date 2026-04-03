from app.repositories.endpoint_repository import EndpointRepository


class EndpointRegistryService:
    def __init__(self, repo: EndpointRepository | None = None):
        self.repo = repo or EndpointRepository()

    def get_endpoint(self, key: str) -> dict:
        return self.repo.get_by_key(key)
