# 文件路径: src/tools/search/arxiv_search.py
# -*- coding: utf-8 -*-
"""
ArXiv 文献检索示例。
使用 ArXiv API 搜索文献并解析结果。
"""
import time
import urllib.parse
import requests
from typing import List, Dict, Any # Ensure List, Dict, Any are imported
import xml.etree.ElementTree as ET # For parsing XML Atom feed
import logging

logger = logging.getLogger(__name__)

def arxiv_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    ArXiv API 查询示例，返回格式：
    [
      {"title": "...", "content": "...", "url": "...", "score": 0.0, "source": "arxiv"},
      ...
    ]
    """
    base_url = "http://export.arxiv.org/api/query"
    # ArXiv API requires terms to be prefixed, e.g., all:, ti: (title), au: (author)
    # Using 'all:' for general search. For more specific searches, this could be customized.
    search_query = f"all:{urllib.parse.quote(query)}"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": k,
        "sortBy": "relevance", # Options: relevance, lastUpdatedDate, submittedDate
        "sortOrder": "descending"
    }

    logger.info(f"开始 ArXiv 搜索，查询: '{query}', 最大结果数: {k}")

    try:
        response = requests.get(base_url, params=params, timeout=20) # Increased timeout for API
        response.raise_for_status() # Check for HTTP errors

        # ArXiv API returns Atom XML feed
        xml_data = response.text
        root = ET.fromstring(xml_data)

        # Atom feed namespace
        # Namespace is often like '{http://www.w3.org/2005/Atom}tag_name'
        # Or sometimes it's default, so no prefix is needed if properly registered or handled.
        # For simplicity, let's try to find tags that might be namespace-prefixed.
        # A common way to handle namespaces with ElementTree is to extract it first if possible.

        # Try to find the namespace from the root element if it exists
        ns_match = ET.register_namespace_("", "http://www.w3.org/2005/Atom") # Common Atom namespace
        # If the above doesn't work directly in findall, you might need to prefix tags like '{http://www.w3.org/2005/Atom}entry'
        # For simplicity, let's assume common tag names for now, or that the default namespace works.

        atom_ns = "{http://www.w3.org/2005/Atom}" # Define the Atom namespace

        results: List[Dict[str, Any]] = []
        for entry in root.findall(f"{atom_ns}entry"):
            title_element = entry.find(f"{atom_ns}title")
            summary_element = entry.find(f"{atom_ns}summary")
            id_element = entry.find(f"{atom_ns}id") # This is usually the ArXiv ID URL
            # Authors can be multiple, concatenate them
            authors_elements = entry.findall(f"{atom_ns}author/{atom_ns}name")
            authors = ", ".join([auth.text.strip() for auth in authors_elements if auth.text]) if authors_elements else "未知作者"


            title = title_element.text.strip().replace("\n", " ") if title_element is not None and title_element.text else "无标题"
            summary = summary_element.text.strip().replace("\n", " ") if summary_element is not None and summary_element.text else "无摘要"
            # The 'id' tag usually contains the link to the PDF or abstract page.
            # ArXiv ID is often like http://arxiv.org/abs/xxxx.xxxx
            url = id_element.text.strip() if id_element is not None and id_element.text else ""
            # Convert ArXiv abstract page URL to PDF URL if desired
            if "/abs/" in url:
                pdf_url = url.replace("/abs/", "/pdf/") + ".pdf" # Often works
            else:
                pdf_url = url # Fallback to original URL

            results.append({
                "title": title,
                "content": summary, # Using summary as content
                "url": url,       # Link to abstract page
                "pdf_url": pdf_url, # Direct link to PDF
                "authors": authors,
                "score": 0.0,     # ArXiv API doesn't provide a relevance score directly in results
                "source": "arxiv"
            })
            if len(results) >= k: # Ensure we don't exceed k results
                break

        logger.info(f"ArXiv 搜索返回 {len(results)} 条结果。")
        return results

    except requests.exceptions.RequestException as req_err:
        logger.error(f"ArXiv API 请求失败: {req_err}", exc_info=True)
        return []
    except ET.ParseError as xml_err:
        logger.error(f"解析 ArXiv API XML 响应失败: {xml_err} - 响应文本: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"处理 ArXiv 搜索结果时发生未知错误: {e}", exc_info=True)
        return []
