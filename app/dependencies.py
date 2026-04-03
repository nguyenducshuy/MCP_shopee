from app.services.cache_service import CacheService
from app.services.sheets_service import SheetsService
from app.repositories.shop_repository import ShopRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.services.shop_registry_service import ShopRegistryService
from app.services.token_service import TokenService
from app.services.sign_service import SignService
from app.services.endpoint_registry_service import EndpointRegistryService
from app.services.auth_service import AuthService
from app.services.shopee_client import ShopeeClient
from app.adapters.shopee_http_adapter import ShopeeHttpAdapter

# Cache & Sheets (singleton)
cache_service = CacheService()
sheets_service = SheetsService()

# Repositories
shop_repo = ShopRepository()
token_repo = TokenRepository(shop_repo=shop_repo)
endpoint_repo = EndpointRepository()

# Services
shop_registry_service = ShopRegistryService(repo=shop_repo)
sign_service = SignService()
token_service = TokenService(token_repo=token_repo)
endpoint_registry_service = EndpointRegistryService(repo=endpoint_repo)
http_adapter = ShopeeHttpAdapter()

auth_service = AuthService(sign_service=sign_service, http_adapter=http_adapter)
token_service.set_auth_service(auth_service)

shopee_client = ShopeeClient(
    shop_registry_service=shop_registry_service,
    token_service=token_service,
    sign_service=sign_service,
    endpoint_registry_service=endpoint_registry_service,
    http_adapter=http_adapter,
)
