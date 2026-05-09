"""CityFlow 中间件集合。"""

from backend.middleware.compression import CompressionMiddleware
from backend.middleware.config import ConfigMiddleware
from backend.middleware.error_handler import setup_error_handlers
from backend.middleware.locale import LocaleMiddleware
from backend.middleware.performance import PerformanceMiddleware
from backend.middleware.pipeline import (ConditionalMiddleware,
                                         MiddlewarePipeline)
from backend.middleware.prometheus import PrometheusMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.security import SecurityHeadersMiddleware
from backend.middleware.session import SessionMiddleware
from backend.middleware.shutdown import ShutdownMiddleware
from backend.middleware.validation import InputValidationMiddleware
from backend.middleware.version import APIVersionMiddleware

__all__ = [
    "APIVersionMiddleware",
    "CompressionMiddleware",
    "ConditionalMiddleware",
    "ConfigMiddleware",
    "LocaleMiddleware",
    "MiddlewarePipeline",
    "PerformanceMiddleware",
    "PrometheusMiddleware",
    "RateLimitMiddleware",
    "ShutdownMiddleware",
    "InputValidationMiddleware",
    "SecurityHeadersMiddleware",
    "SessionMiddleware",
    "setup_error_handlers",
]
