#!/usr/bin/env python3
"""
Issnu PDF下载器主入口脚本

使用方法:
    python download.py
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

    # 创建爬虫实例
    crawler = IssuuCrawler(
        max_retries=3,
        timeout=60,
        min_delay=2.0,
        max_delay=5.0,
        headless=True
    )

    # 执行下载
    success = crawler.download_pdf(url, save_path)

    if success:
        print(f"\n✅ PDF下载成功!")
        print(f"📁 文件保存位置: {save_path}")
        sys.exit(0)
    else:
        print(f"\n❌ PDF下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
