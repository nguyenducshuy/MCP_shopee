class ShopeeMCPError(Exception):
    pass


class ShopNotFoundError(ShopeeMCPError):
    pass


class TokenNotFoundError(ShopeeMCPError):
    pass


class TokenExpiredError(ShopeeMCPError):
    pass


class RefreshTokenExpiredError(TokenExpiredError):
    """Refresh token hết hạn — cần user authorize lại shop."""
    pass


class ShopeeAPIError(ShopeeMCPError):
    def __init__(self, error_code: str = "", error_msg: str = "", request_id: str = ""):
        self.error_code = error_code
        self.error_msg = error_msg
        self.request_id = request_id
        super().__init__(f"Shopee API Error [{error_code}]: {error_msg}")
