"""Rate limiting configuration for OpenInsure.

Provides a shared ``Limiter`` instance used by both ``main.py`` (middleware
registration) and individual routers (endpoint-specific limits).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
