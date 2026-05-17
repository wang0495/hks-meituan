"""CityFlow 中间件集合。"""

from backend.middleware.config import ConfigMiddleware
from backend.middleware.error_handler import setup_error_handlers
from backend.middleware.prometheus import PrometheusMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.security import SecurityHeadersMiddleware
from backend.middleware.session import SessionMiddleware
from backend.middleware.shutdown import ShutdownMiddleware
from backend.middleware.validation import InputValidationMiddleware
from backend.middleware.version import APIVersionMiddleware

__all__ = [
    "APIVersionMiddleware",
    "ConfigMiddleware",
    "PrometheusMiddleware",
    "RateLimitMiddleware",
    "ShutdownMiddleware",
    "InputValidationMiddleware",
    "SecurityHeadersMiddleware",
    "SessionMiddleware",
    "setup_error_handlers",
]
