# Shopee auth paths
AUTH_PARTNER_PATH = "/api/v2/shop/auth_partner"
TOKEN_GET_PATH = "/api/v2/auth/token/get"
TOKEN_REFRESH_PATH = "/api/v2/auth/access_token/get"

# Token lifetime defaults (Shopee spec)
ACCESS_TOKEN_LIFETIME = 4 * 3600        # 4 giờ
REFRESH_TOKEN_LIFETIME = 30 * 24 * 3600  # 30 ngày
