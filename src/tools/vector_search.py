# 文件路径: src/tools/vector_search.py
# -*- coding: utf-8 -*-
# 定义向量存储与检索引脚
import json
import faiss
import numpy as np
import threading
import os
from langchain_core.tools import tool, BaseTool
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional

# 修复：引入 FAISS, HuggingFaceEmbeddings, Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from .decorators import log_io
from src.config.configuration import Configuration

# 线程锁，用于保证并发访问索引时的安全
_lock = threading.Lock()
# 全局缓存，用于存储已加载的嵌入模型和FAISS索引实例
_model_cache: Optional[SentenceTransformer] = None
_index_cache: Dict[str, faiss.Index] = {}
_metadata_cache: Dict[str, List[str]] = {}


def _get_embedding_model() -> SentenceTransformer:
    """惰性加载嵌入模型以节省启动时间，并确保线程安全。"""
    global _model_cache
    if _model_cache is None:
        with _lock:
            if _model_cache is None:
                print("--- [知识库] 首次加载嵌入模型... ---")
                _model_cache = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    return _model_cache


def _get_index(config: Configuration) -> Optional[faiss.IndexIDMap]:
    """加载或创建FAISS索引，并缓存起来。"""
    index_path = f"{config.vector_store_path}.faiss"
    metadata_path = f"{config.vector_store_path}.meta.json"

    with _lock:
        if index_path in _index_cache:
            return _index_cache[index_path]

        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        if os.path.exists(index_path):
            print(f"--- [知识库] 正在从 {index_path} 加载索引... ---")
            index = faiss.read_index(index_path)
            with open(metadata_path, "r", encoding="utf-8") as f:
                _metadata_cache[index_path] = json.load(f)
        else:
            print("--- [知识库] 未找到现有索引，将创建新索引。 ---")
            model = _get_embedding_model()
            dimension = model.get_sentence_embedding_dimension()
            index = faiss.IndexIDMap(faiss.IndexFlatL2(dimension))
            _metadata_cache[index_path] = []

        _index_cache[index_path] = index
        return index


@tool
@log_io
def vector_search_tool(query: str, k: int = 3, *, config: Optional[Configuration] = None) -> List[Dict[str, Any]]:
    """
    使用此工具在历史研究摘要的向量存储中搜索相似内容。
    简化注释：向量搜索历史记录
    """
    if config is None:
        config = Configuration.from_runnable_config()

    index = _get_index(config)
    metadata_path = f"{config.vector_store_path}.meta.json"
    metadata = _metadata_cache.get(metadata_path, [])

    if index is None or index.ntotal == 0:
        return [{"content": "向量知识库为空，无历史记录可供查询。"}]

    model = _get_embedding_model()
    query_embedding = model.encode([query])

    with _lock:
        distances, indices = index.search(query_embedding, k)

    results = []
    for i in range(len(indices[0])):
        idx = indices[0][i]
        if idx != -1 and idx < len(metadata):
            results.append({
                "content": metadata[idx],
                "distance": float(distances[0][i])
            })
    return results


def add_to_vector_store(texts: List[str], *, config: Optional[Configuration] = None):
    """
    将新的文本摘要添加到向量存储中，并确保线程安全。
    简化注释：添加内容到知识库
    """
    if not texts:
        return
    if config is None:
        config = Configuration.from_runnable_config()

    model = _get_embedding_model()
    new_embeddings = model.encode(texts).astype('float32')
    index = _get_index(config)

    metadata_path = f"{config.vector_store_path}.meta.json"
    index_path = f"{config.vector_store_path}.faiss"

    with _lock:
        start_id = index.ntotal
        ids = np.arange(start_id, start_id + len(texts))
        index.add_with_ids(new_embeddings, ids)

        # 更新元数据并保存
        _metadata_cache.setdefault(metadata_path, []).extend(texts)
        faiss.write_index(index, index_path)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(_metadata_cache[metadata_path], f, ensure_ascii=False, indent=2)

    print(f"--- [知识库] 已添加 {len(texts)} 条新记录，索引已保存。 ---")


# 修复：将 get_retriever_tool 的占位符实现替换为完整功能
def get_retriever_tool(resources: List[str], config: Configuration) -> Optional[BaseTool]:
    """
    根据本地文件资源创建并返回一个 FAISS 向量检索器工具。
    简化注释：获取本地文件检索器工具
    """
    if not resources:
        return None

    # 定义嵌入模型
    # 使用社区推荐的、轻量且高效的模型
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'})

    # 读取文件内容并创建文档
    docs = []
    for file_path in resources:
        try:
            # 确保文件存在
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    doc = Document(page_content=content, metadata={"source": file_path})
                    docs.append(doc)
            else:
                print(f"--- [本地检索] 警告：资源文件未找到，已跳过：{file_path} ---")
        except Exception as e:
            print(f"--- [本地检索] 错误：读取文件 {file_path} 失败: {e} ---")

    if not docs:
        print("--- [本地检索] 警告：未能成功加载任何本地文档。---")
        return None

    # 基于文档创建 FAISS 向量存储
    print(f"--- [本地检索] 正在为 {len(docs)} 个文档创建向量索引... ---")
    try:
        vector_store = FAISS.from_documents(docs, embeddings)
        retriever = vector_store.as_retriever(search_kwargs={"k": config.max_search_results})
    except Exception as e:
        print(f"--- [本地检索] 错误：创建 FAISS 索引失败: {e} ---")
        return None


    # 将检索器包装成一个 LangChain 工具
    @tool("local_search_tool")
    def local_search_tool(query: str) -> str:
        """
        当你需要从用户提供的本地文件中检索信息时，使用此工具。
        输入是你希望查询的内容。
        返回最相关的文本片段。
        """
        try:
            print(f"--- [本地检索] 正在使用查询 '{query}' 检索本地文件... ---")
            results = retriever.get_relevant_documents(query)
            if not results:
                return "在本地文件中没有找到相关内容。"
            # 将结果拼接成一个字符串返回
            return "\n\n".join([f"来源: {doc.metadata.get('source', '未知')}\n内容: {doc.page_content}" for doc in results])
        except Exception as e:
            return f"本地文件检索失败: {e}"

    return local_search_tool