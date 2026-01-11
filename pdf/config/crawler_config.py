"""
Issuu爬虫配置文件

所有配置都可以通过环境变量覆盖
"""

import os

# 等待策略列表（按优先级从高到低）
WAIT_STRATEGIES = [
    'domcontentloaded',  # 最快，等待DOM加载完成
    'load',            # 中等，等待页面完全加载
    'networkidle',     # 最慢，等待所有网络请求完成
]

# 代理配置（通过环境变量设置）
# 示例: export HTTP_PROXY=http://proxy.example.com:8080
PROXY_URL = os.getenv('HTTP_PROXY', None)

# 页面加载超时时间（毫秒）
PAGE_LOAD_TIMEOUT = int(os.getenv('PAGE_LOAD_TIMEOUT', 60000))  # 默认60秒

# 是否禁用图片加载（加快页面加载速度）
DISABLE_IMAGES = os.getenv('DISABLE_IMAGES', 'true').lower() == 'true'

# 浏览器启动参数
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',  # 隐藏自动化标识
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-web-security',
]

# 是否使用无头模式
HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'

# 最大重试次数
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# 最小随机延迟（秒）
MIN_DELAY = float(os.getenv('MIN_DELAY', '2.0'))

# 最大随机延迟（秒）
MAX_DELAY = float(os.getenv('MAX_DELAY', '5.0'))

# 浏览器视口配置
VIEWPORT_WIDTH = int(os.getenv('VIEWPORT_WIDTH', '1920'))
VIEWPORT_HEIGHT = int(os.getenv('VIEWPORT_HEIGHT', '1080'))

# 时区设置（模拟真实用户）
TIMEZONE_ID = os.getenv('TIMEZONE_ID', 'America/New_York')

# 语言设置
LOCALE = os.getenv('LOCALE', 'en-US')

# 是否启用详细日志
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
