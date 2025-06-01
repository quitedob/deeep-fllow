# -*- coding: utf-8 -*-
# 对 Tavily 搜索工具的扩展，使其能处理和返回图片

from langchain_community.tools.tavily_search import TavilySearchResults


class TavilySearchResultsWithImages(TavilySearchResults):
    """
    一个版本的 TavilySearchResults，它也会在结果中包含图片URL。
    简化注释：带图片的Tavily搜索
    """
    include_images: bool = True

    def _process_results(self, results: list) -> str:
        """
        处理搜索结果，格式化为字符串。
        简化注释：处理并格式化结果
        """
        processed_results = []
        for res in results:
            item = f"来源: {res['url']}\n内容: {res['content']}"
            if self.include_images and "images" in res and res["images"]:
                item += "\n图片: " + ", ".join(res["images"])
            processed_results.append(item)

        return "\n\n".join(processed_results)