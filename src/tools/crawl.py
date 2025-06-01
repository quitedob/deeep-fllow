# 文件路径: src/tools/crawl.py
# -*- coding: utf-8 -*-
# 实现网页抓取功能

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from src.crawler.article import Article
from src.crawler.readability_extractor import ReadabilityExtractor


class Crawler:
    """
    一个健壮的网页抓取器，增加了自动重试功能。
    简化注释：网页抓取器
    """

    def __init__(self, headers=None):
        if headers is None:
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        else:
            self.headers = headers

        # 配置带重试逻辑的 Session
        self.session = requests.Session()
        retries = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 退避因子，每次重试间隔时间会增加
            status_forcelist=[429, 500, 502, 503, 504],  # 对这些状态码进行重试
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def crawl(self, url: str) -> Article:
        """
        抓取指定URL并提取文章内容
        简化注释：抓取URL并提取内容
        """
        try:
            # 使用配置好的 session 对象进行请求
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            extractor = ReadabilityExtractor()
            title, content_html = extractor.extract(response.text, url)

            soup = BeautifulSoup(content_html, "lxml")
            content_text = soup.get_text(separator="\n", strip=True)

            return Article(url=url, title=title, content=content_text)

        except requests.RequestException as e:
            raise ConnectionError(f"抓取URL时发生网络错误 (已重试): {url}, Error: {e}")

# 修复：新增一个使用 @tool 装饰的函数，使其能被 LangChain 正确识别和调用
@tool("crawl_tool")
def crawl_tool(url: str) -> str:
    """
    当你需要从指定的URL中提取正文内容时，使用此工具。
    输入应该是一个有效的URL字符串。
    输出是提取的文章纯文本内容。
    """
    try:
        crawler = Crawler()
        article = crawler.crawl(url)
        return article.content
    except Exception as e:
        return f"抓取失败: {e}"