"""
配置模块
"""

from .crawler_config import (
    WAIT_STRATEGIES,
    PROXY_URL,
    PAGE_LOAD_TIMEOUT,
    DISABLE_IMAGES,
    BROWSER_ARGS,
    HEADLESS,
    MAX_RETRIES,
    MIN_DELAY,
    MAX_DELAY,
)

__all__ = [
    'WAIT_STRATEGIES',
    'PROXY_URL',
    'PAGE_LOAD_TIMEOUT',
    'DISABLE_IMAGES',
    'BROWSER_ARGS',
    'HEADLESS',
    'MAX_RETRIES',
    'MIN_DELAY',
    'MAX_DELAY',
]
