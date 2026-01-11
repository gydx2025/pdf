"""
Issuu PDF爬虫模块

使用Playwright自动化下载Issuu上的PDF文档
支持User-Agent轮换、随机延迟、多级等待策略和错误重试机制
"""

import os
import random
import re
import time
import logging
from typing import Optional
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# 导入配置
try:
    from config import (
        WAIT_STRATEGIES,
        PROXY_URL,
        PAGE_LOAD_TIMEOUT,
        DISABLE_IMAGES,
        BROWSER_ARGS,
        HEADLESS,
        MAX_RETRIES,
        MIN_DELAY,
        MAX_DELAY,
        VIEWPORT_WIDTH,
        VIEWPORT_HEIGHT,
        TIMEZONE_ID,
        LOCALE,
        DEBUG,
    )
except ImportError:
    # 如果配置模块不存在，使用默认值
    WAIT_STRATEGIES = ['domcontentloaded', 'load', 'networkidle']
    PROXY_URL = None
    PAGE_LOAD_TIMEOUT = 60000
    DISABLE_IMAGES = True
    BROWSER_ARGS = [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox',
    ]
    HEADLESS = True
    MAX_RETRIES = 3
    MIN_DELAY = 2.0
    MAX_DELAY = 5.0
    VIEWPORT_WIDTH = 1920
    VIEWPORT_HEIGHT = 1080
    TIMEZONE_ID = 'America/New_York'
    LOCALE = 'en-US'
    DEBUG = False

# 配置日志
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IssuuCrawler:
    """Issuu PDF下载爬虫类"""

    # User-Agent列表，用于轮换
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(
        self,
        max_retries: Optional[int] = None,
        timeout: Optional[int] = None,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        headless: Optional[bool] = None,
        proxy_url: Optional[str] = None,
        disable_images: Optional[bool] = None,
    ):
        """
        初始化爬虫

        Args:
            max_retries: 最大重试次数（默认使用配置文件值）
            timeout: 超时时间（毫秒，默认使用配置文件值）
            min_delay: 最小随机延迟（秒，默认使用配置文件值）
            max_delay: 最大随机延迟（秒，默认使用配置文件值）
            headless: 是否使用无头模式（默认使用配置文件值）
            proxy_url: 代理URL（默认使用配置文件值）
            disable_images: 是否禁用图片（默认使用配置文件值）
        """
        self.max_retries = max_retries if max_retries is not None else MAX_RETRIES
        self.timeout = timeout if timeout is not None else PAGE_LOAD_TIMEOUT
        self.min_delay = min_delay if min_delay is not None else MIN_DELAY
        self.max_delay = max_delay if max_delay is not None else MAX_DELAY
        self.headless = headless if headless is not None else HEADLESS
        self.proxy_url = proxy_url if proxy_url is not None else PROXY_URL
        self.disable_images = disable_images if disable_images is not None else DISABLE_IMAGES

        logger.info("=" * 60)
        logger.info("Issuu爬虫配置:")
        logger.info(f"  最大重试次数: {self.max_retries}")
        logger.info(f"  超时时间: {self.timeout}ms ({self.timeout/1000:.1f}s)")
        logger.info(f"  延迟范围: {self.min_delay}-{self.max_delay}秒")
        logger.info(f"  无头模式: {self.headless}")
        logger.info(f"  代理配置: {self.proxy_url or '未设置'}")
        logger.info(f"  禁用图片: {self.disable_images}")
        logger.info(f"  等待策略: {WAIT_STRATEGIES}")
        logger.info("=" * 60)

    def _get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return random.choice(self.USER_AGENTS)

    def _random_delay(self) -> None:
        """随机延迟"""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"延迟 {delay:.2f} 秒")
        time.sleep(delay)

    def _setup_page(self, page: Page) -> None:
        """
        配置页面设置

        Args:
            page: Playwright页面对象
        """
        # 设置视口和时区
        page.set_viewport_size({'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT})
        
        # 禁用图片加载
        if self.disable_images:
            def handle_route(route, request):
                if request.resource_type in ['image', 'media', 'font']:
                    route.abort()
                else:
                    route.continue_()
            page.route('**/*', handle_route)
            logger.debug("已禁用图片、媒体和字体加载")

    def _open_page_with_strategy(self, page: Page, url: str) -> bool:
        """
        使用多级等待策略打开页面

        Args:
            page: Playwright页面对象
            url: 要打开的URL

        Returns:
            是否成功打开页面
        """
        page.set_default_timeout(self.timeout)

        for strategy_index, strategy in enumerate(WAIT_STRATEGIES):
            strategy_name = strategy
            attempt_start = time.time()
            
            try:
                logger.info(f"使用等待策略: {strategy_name} (阶段 {strategy_index + 1}/{len(WAIT_STRATEGIES)})")
                page.goto(url, wait_until=strategy, timeout=self.timeout)
                
                elapsed = time.time() - attempt_start
                logger.info(f"✅ 页面加载成功 ({strategy_name}) - 耗时: {elapsed:.2f}秒")
                return True
                
            except PlaywrightTimeoutError as e:
                elapsed = time.time() - attempt_start
                logger.warning(f"⏱️  等待策略 '{strategy_name}' 超时 - 耗时: {elapsed:.2f}秒")
                
                # 如果不是最后一个策略，尝试从已加载的DOM中提取PDF
                if strategy_index < len(WAIT_STRATEGIES) - 1:
                    logger.info("尝试从已加载的DOM中提取PDF链接...")
                    pdf_url = self._extract_pdf_url_from_dom(page)
                    if pdf_url:
                        logger.info(f"✅ 从DOM中成功提取PDF链接")
                        # 将PDF URL存储在page对象中
                        page.pdf_url = pdf_url
                        return True
                    logger.info("DOM中未找到PDF链接，尝试下一个等待策略...")
                else:
                    # 最后一个策略也失败了，最后一次尝试提取
                    logger.info("最后尝试从已加载的DOM中提取PDF链接...")
                    pdf_url = self._extract_pdf_url_from_dom(page)
                    if pdf_url:
                        logger.info(f"✅ 从DOM中成功提取PDF链接")
                        page.pdf_url = pdf_url
                        return True
                    
            except Exception as e:
                elapsed = time.time() - attempt_start
                logger.error(f"❌ 页面加载失败 ({strategy_name}) - 耗时: {elapsed:.2f}秒 - 错误: {e}")
                if strategy_index < len(WAIT_STRATEGIES) - 1:
                    continue
                return False

        return False

    def _extract_pdf_url_from_dom(self, page: Page) -> Optional[str]:
        """
        从DOM中提取PDF链接（用于部分加载情况）

        Args:
            page: Playwright页面对象

        Returns:
            PDF下载链接，如果未找到返回None
        """
        logger.debug("开始从DOM中提取PDF链接...")
        
        # 获取页面内容
        try:
            page_content = page.content()
            
            # 方法1：查找所有http/https链接
            pdf_urls = re.findall(r'https?://[^\s"\']+\.pdf', page_content)
            if pdf_urls:
                logger.info(f"从HTML内容中找到 {len(pdf_urls)} 个PDF链接")
                return pdf_urls[0]
            
            # 方法2：查找Issuu特有的资源链接
            # Issuu通常使用documentId来标识文档
            doc_id_match = re.search(r'"documentId":"([^"]+)"', page_content)
            if doc_id_match:
                doc_id = doc_id_match.group(1)
                logger.info(f"找到文档ID: {doc_id}")
                # 构造可能的下载URL
                return f"https://issuu.com/api/v0/document/{doc_id}"
                
            # 方法3：查找data属性中的链接
            data_urls = re.findall(r'data-[a-z-]+url=["\']([^"\']+)["\']', page_content, re.IGNORECASE)
            for url in data_urls:
                if 'pdf' in url.lower() or 'download' in url.lower():
                    logger.info(f"从data属性找到链接: {url}")
                    return url
            
        except Exception as e:
            logger.debug(f"从DOM提取失败: {e}")
        
        logger.debug("DOM中未找到PDF链接")
        return None

    def _get_pdf_url(self, page: Page) -> Optional[str]:
        """
        从页面中提取PDF链接（完整版本）

        Args:
            page: Playwright页面对象

        Returns:
            PDF下载链接，如果未找到返回None
        """
        # 首先检查是否在page对象中存储了PDF URL
        if hasattr(page, 'pdf_url') and page.pdf_url:
            return page.pdf_url
        
        logger.debug("开始查找PDF链接...")
        
        # 方法1：查找PDF下载按钮或链接
        try:
            # 尝试查找直接PDF链接
            pdf_link = page.locator('a[href*=".pdf"]').first
            if pdf_link.is_visible(timeout=5000):
                href = pdf_link.get_attribute('href')
                if href:
                    logger.info(f"找到PDF链接 (方法1): {href}")
                    return href
        except Exception as e:
            logger.debug(f"方法1未找到PDF链接: {e}")

        # 方法2：查找Issuu内嵌PDF viewer
        try:
            # 查找iframe或embed元素
            iframe = page.locator('iframe[src*="pdf"], embed[type*="pdf"]').first
            if iframe.is_visible(timeout=5000):
                src = iframe.get_attribute('src')
                if src:
                    logger.info(f"找到PDF嵌入源 (方法2): {src}")
                    return src
        except Exception as e:
            logger.debug(f"方法2未找到PDF嵌入: {e}")

        # 方法3：查找download按钮
        try:
            download_btn = page.locator('button:has-text("Download"), a:has-text("Download PDF"), button[title*="download"], button[aria-label*="download"]').first
            if download_btn.is_visible(timeout=5000):
                logger.info("找到下载按钮，尝试点击...")
                # 点击下载按钮
                download_btn.click()
                self._random_delay()
                # 获取当前URL或查找PDF链接
                logger.info(f"当前页面URL: {page.url}")
                # 尝试从页面变化中获取下载链接
                return page.url
        except Exception as e:
            logger.debug(f"方法3点击下载按钮失败: {e}")

        # 方法4：查找文档查看器中的PDF源
        try:
            # 查找class包含docViewer的元素
            viewer = page.locator('.document-viewer, .issuu-viewer, [class*="viewer"]').first
            if viewer.is_visible(timeout=5000):
                logger.debug("找到文档查看器")
                # 获取viewer内的iframe
                pdf_frame = viewer.locator('iframe').first
                if pdf_frame.is_visible(timeout=3000):
                    src = pdf_frame.get_attribute('src')
                    if src:
                        logger.info(f"找到viewer内的PDF源 (方法4): {src}")
                        return src
        except Exception as e:
            logger.debug(f"方法4未找到viewer: {e}")

        # 方法5：执行JavaScript查找PDF资源
        try:
            logger.debug("尝试通过JavaScript查找PDF资源...")
            js_code = """
            () => {
                // 查找所有包含pdf的URL
                const links = Array.from(document.querySelectorAll('a[href]'));
                const pdfLinks = links.filter(a => a.href.includes('.pdf'));
                if (pdfLinks.length > 0) return pdfLinks[0].href;
                
                // 查找所有iframe和embed
                const frames = Array.from(document.querySelectorAll('iframe, embed'));
                for (const frame of frames) {
                    if (frame.src && (frame.src.includes('pdf') || frame.src.includes('document'))) {
                        return frame.src;
                    }
                }
                
                // 查找window对象中的配置
                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.document) {
                    return window.__INITIAL_STATE__.document.url;
                }
                
                return null;
            }
            """
            pdf_url = page.evaluate(js_code)
            if pdf_url:
                logger.info(f"JavaScript找到PDF链接 (方法5): {pdf_url}")
                return pdf_url
        except Exception as e:
            logger.debug(f"方法5 JavaScript查找失败: {e}")

        # 方法6：从所有链接中查找
        try:
            all_links = page.locator('a[href]').all()
            logger.debug(f"找到 {len(all_links)} 个链接")
            for link in all_links:
                href = link.get_attribute('href')
                if href and ('pdf' in href.lower() or 'download' in href.lower()):
                    logger.info(f"找到可能的下载链接 (方法6): {href}")
                    return href
        except Exception as e:
            logger.debug(f"方法6查找所有链接失败: {e}")

        logger.warning("所有方法都未能找到PDF下载链接")
        return None

    def _download_file(self, url: str, save_path: str) -> bool:
        """
        下载文件

        Args:
            url: 文件URL
            save_path: 保存路径

        Returns:
            是否下载成功
        """
        download_start = time.time()
        
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'application/pdf,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://issuu.com/',
            }
            
            logger.info(f"开始下载: {url}")
            
            # 如果使用代理
            proxies = None
            if self.proxy_url:
                proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url,
                }
                logger.info(f"使用代理: {self.proxy_url}")
            
            response = requests.get(
                url, 
                headers=headers, 
                timeout=self.timeout / 1000,  # 转换为秒
                stream=True,
                proxies=proxies
            )
            response.raise_for_status()

            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 保存文件
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if progress % 10 < 1:  # 每10%输出一次
                                logger.debug(f"下载进度: {progress:.1f}%")

            elapsed = time.time() - download_start
            file_size = os.path.getsize(save_path)
            
            logger.info(f"✅ 文件已保存: {save_path}")
            logger.info(f"   大小: {file_size / 1024:.2f} KB")
            logger.info(f"   耗时: {elapsed:.2f}秒")
            
            return True

        except requests.exceptions.ProxyError as e:
            logger.error(f"❌ 代理错误: {e}")
            logger.error(f"   代理URL: {self.proxy_url}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ 下载超时: {e}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP错误: {e}")
            logger.error(f"   状态码: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
            return False
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            return False

    def _download_direct_url(self, url: str, save_path: str) -> bool:
        """
        直接下载URL（不使用浏览器，用于已知PDF链接）

        Args:
            url: PDF下载链接
            save_path: 保存路径

        Returns:
            是否下载成功
        """
        logger.info("尝试直接下载URL...")
        return self._download_file(url, save_path)

    def download_pdf(self, url: str, save_path: str) -> bool:
        """
        下载PDF文件

        Args:
            url: Issuu文档URL
            save_path: 本地保存路径

        Returns:
            是否下载成功
        """
        logger.info("=" * 60)
        logger.info("开始下载PDF")
        logger.info("=" * 60)
        logger.info(f"URL: {url}")
        logger.info(f"保存路径: {save_path}")
        logger.info("=" * 60)

        total_start = time.time()

        for attempt in range(1, self.max_retries + 1):
            attempt_start = time.time()
            logger.info(f"\n🔄 尝试 {attempt}/{self.max_retries}")
            logger.info("-" * 60)

            try:
                self._random_delay()

                with sync_playwright() as p:
                    # 启动浏览器
                    browser = p.chromium.launch(
                        headless=self.headless,
                        args=BROWSER_ARGS
                    )
                    
                    # 创建浏览器上下文
                    context_options = {
                        'user_agent': self._get_random_user_agent(),
                        'viewport': {'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
                        'locale': LOCALE,
                        'timezone_id': TIMEZONE_ID,
                    }
                    
                    # 添加代理配置
                    if self.proxy_url:
                        context_options['proxy'] = {'server': self.proxy_url}
                        logger.info(f"✓ 浏览器已配置代理: {self.proxy_url}")
                    
                    context = browser.new_context(**context_options)
                    page = context.new_page()

                    # 配置页面
                    self._setup_page(page)

                    # 使用多级等待策略打开页面
                    page_loaded = self._open_page_with_strategy(page, url)

                    if not page_loaded:
                        logger.error(f"❌ 页面加载失败 (尝试 {attempt}/{self.max_retries})")
                        browser.close()
                        continue

                    # 查找PDF链接
                    logger.info("正在查找PDF下载链接...")
                    pdf_url = self._get_pdf_url(page)

                    if pdf_url:
                        # 如果是相对URL，转换为绝对URL
                        if pdf_url.startswith('/'):
                            from urllib.parse import urljoin
                            pdf_url = urljoin(url, pdf_url)

                        logger.info(f"✅ 找到PDF链接: {pdf_url}")
                        logger.info(f"开始下载PDF文件...")
                        
                        if self._download_file(pdf_url, save_path):
                            elapsed = time.time() - total_start
                            logger.info("=" * 60)
                            logger.info(f"✅ PDF下载成功! 总耗时: {elapsed:.2f}秒")
                            logger.info("=" * 60)
                            browser.close()
                            return True
                    else:
                        logger.warning(f"⚠️  未找到PDF链接 (尝试 {attempt}/{self.max_retries})")

                    browser.close()

            except PlaywrightTimeoutError as e:
                logger.warning(f"⏱️  页面加载超时 (尝试 {attempt}/{self.max_retries}): {e}")
            except Exception as e:
                logger.error(f"❌ 下载失败 (尝试 {attempt}/{self.max_retries}): {e}")
                import traceback
                logger.debug(traceback.format_exc())

            # 重试前等待
            if attempt < self.max_retries:
                wait_time = random.uniform(5, 10)
                logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                time.sleep(wait_time)

        total_elapsed = time.time() - total_start
        logger.error("=" * 60)
        logger.error(f"❌ PDF下载失败，已达到最大重试次数: {self.max_retries}")
        logger.error(f"   总耗时: {total_elapsed:.2f}秒")
        logger.error("=" * 60)
        return False
