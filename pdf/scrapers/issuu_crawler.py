"""
Issuu PDF爬虫模块

使用Playwright自动化下载Issuu上的PDF文档
支持User-Agent轮换、随机延迟和错误重试机制
"""

import os
import random
import time
import logging
from typing import Optional
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
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
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(
        self,
        max_retries: int = 3,
        timeout: int = 60,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        headless: bool = True
    ):
        """
        初始化爬虫

        Args:
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            min_delay: 最小随机延迟（秒）
            max_delay: 最大随机延迟（秒）
            headless: 是否使用无头模式
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.headless = headless

    def _get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return random.choice(self.USER_AGENTS)

    def _random_delay(self) -> None:
        """随机延迟"""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"延迟 {delay:.2f} 秒")
        time.sleep(delay)

    def _get_pdf_url(self, page: Page) -> Optional[str]:
        """
        从页面中提取PDF链接

        Args:
            page: Playwright页面对象

        Returns:
            PDF下载链接，如果未找到返回None
        """
        # 方法1：查找PDF下载按钮或链接
        try:
            # 尝试查找直接PDF链接
            pdf_link = page.locator('a[href*=".pdf"]').first
            if pdf_link.is_visible(timeout=5000):
                href = pdf_link.get_attribute('href')
                if href:
                    logger.info(f"找到PDF链接: {href}")
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
                    logger.info(f"找到PDF嵌入源: {src}")
                    return src
        except Exception as e:
            logger.debug(f"方法2未找到PDF嵌入: {e}")

        # 方法3：查找download按钮
        try:
            download_btn = page.locator('button:has-text("Download"), a:has-text("Download PDF")').first
            if download_btn.is_visible(timeout=5000):
                # 点击下载按钮
                download_btn.click()
                self._random_delay()
                # 获取当前URL或查找PDF链接
                return page.url
        except Exception as e:
            logger.debug(f"方法3点击下载按钮失败: {e}")

        # 方法4：查找文档查看器中的PDF源
        try:
            # 查找class包含docViewer的元素
            viewer = page.locator('.document-viewer, .issuu-viewer, [class*="viewer"]').first
            if viewer.is_visible(timeout=5000):
                # 获取viewer内的iframe
                pdf_frame = viewer.locator('iframe').first
                if pdf_frame.is_visible(timeout=3000):
                    src = pdf_frame.get_attribute('src')
                    if src:
                        logger.info(f"找到viewer内的PDF源: {src}")
                        return src
        except Exception as e:
            logger.debug(f"方法4未找到viewer: {e}")

        logger.warning("未能找到PDF下载链接")
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
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'application/pdf,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()

            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"文件已保存: {save_path}")
            return True

        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False

    def download_pdf(self, url: str, save_path: str) -> bool:
        """
        下载PDF文件

        Args:
            url: Issuu文档URL
            save_path: 本地保存路径

        Returns:
            是否下载成功
        """
        logger.info(f"开始下载PDF: {url}")
        logger.info(f"保存路径: {save_path}")

        for attempt in range(1, self.max_retries + 1):
            try:
                self._random_delay()

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=self.headless)
                    context = browser.new_context(
                        user_agent=self._get_random_user_agent(),
                        viewport={'width': 1920, 'height': 1080},
                    )
                    page = context.new_page()

                    # 设置超时
                    page.set_default_timeout(self.timeout * 1000)

                    logger.info(f"尝试 {attempt}/{self.max_retries}: 打开页面")
                    page.goto(url, wait_until='networkidle')

                    # 等待页面加载
                    self._random_delay()

                    # 查找PDF链接
                    pdf_url = self._get_pdf_url(page)

                    if pdf_url:
                        # 如果是相对URL，转换为绝对URL
                        if pdf_url.startswith('/'):
                            from urllib.parse import urljoin
                            pdf_url = urljoin(url, pdf_url)

                        logger.info(f"开始下载PDF文件: {pdf_url}")
                        if self._download_file(pdf_url, save_path):
                            browser.close()
                            return True
                    else:
                        # 如果找不到直接链接，尝试从页面获取完整HTML
                        logger.info("尝试从页面内容提取PDF...")
                        
                        # 查找所有可能的资源链接
                        all_links = page.locator('a[href]').all()
                        for link in all_links:
                            href = link.get_attribute('href')
                            if href and ('pdf' in href.lower() or 'download' in href.lower()):
                                logger.info(f"找到下载链接: {href}")
                                if self._download_file(href, save_path):
                                    browser.close()
                                    return True

                    browser.close()

            except PlaywrightTimeoutError as e:
                logger.warning(f"页面加载超时 (尝试 {attempt}/{self.max_retries}): {e}")
            except Exception as e:
                logger.error(f"下载失败 (尝试 {attempt}/{self.max_retries}): {e}")

            if attempt < self.max_retries:
                wait_time = random.uniform(5, 10)
                logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                time.sleep(wait_time)

        logger.error(f"PDF下载失败，已达到最大重试次数: {self.max_retries}")
        return False
