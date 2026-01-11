#!/usr/bin/env python3
"""
Issuu PDF下载器主入口脚本

使用方法:
    python download.py

环境变量配置:
    HTTP_PROXY              - 代理URL (如: http://proxy.example.com:8080)
    PAGE_LOAD_TIMEOUT       - 页面加载超时时间(毫秒, 默认: 60000)
    DISABLE_IMAGES          - 是否禁用图片 (默认: true)
    HEADLESS                - 是否无头模式 (默认: true)
    MAX_RETRIES             - 最大重试次数 (默认: 3)
    DEBUG                   - 调试模式 (默认: false)
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers import IssuuCrawler


def main():
    """主函数"""
    # 配置参数
    url = "https://issuu.com/vidula.dinesh/docs/vidula_dinesh_issuu"
    save_dir = os.path.join(os.path.dirname(__file__), 'downloads')
    save_path = os.path.join(save_dir, 'vidula_dinesh_issuu.pdf')

    # 创建爬虫实例（使用配置文件中的默认值，也可通过参数覆盖）
    crawler = IssuuCrawler(
        max_retries=None,      # 使用配置文件值
        timeout=None,          # 使用配置文件值
        min_delay=None,        # 使用配置文件值
        max_delay=None,        # 使用配置文件值
        headless=None,         # 使用配置文件值
        proxy_url=None,        # 使用配置文件值
        disable_images=None,   # 使用配置文件值
    )

    # 执行下载
    success = crawler.download_pdf(url, save_path)

    if success:
        print(f"\n✅ PDF下载成功!")
        print(f"📁 文件保存位置: {save_path}")
        sys.exit(0)
    else:
        print(f"\n❌ PDF下载失败")
        print(f"\n💡 提示:")
        print(f"   - 如遇网络问题，可尝试设置代理: export HTTP_PROXY=http://your-proxy:port")
        print(f"   - 启用调试模式查看详细信息: export DEBUG=true")
        print(f"   - 调整超时时间: export PAGE_LOAD_TIMEOUT=90000")
        sys.exit(1)


if __name__ == "__main__":
    main()
