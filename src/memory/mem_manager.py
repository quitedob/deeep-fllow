# -*- coding: utf-8 -*-
"""
长期记忆管理器，封装了与本地向量数据库 (FAISS) 的交互接口。
"""
import os
import faiss
import numpy as np
import threading
import json
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from src.config.configuration import Configuration

# 全局记忆实例和锁
_mem_instance_lock = threading.Lock()
_mem_instance_cache: Dict[str, 'FaissMemoryManager'] = {}


class FaissMemoryManager:
    """使用FAISS和SentenceTransformers实现本地记忆系统"""

    def __init__(self, index_path: str):
        self.index_path = index_path
        self.meta_path = f"{index_path}.meta.json"
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        self.dimension = self.embedder.get_sentence_embedding_dimension()
        self.index = None
        self.metadata_store: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """从磁盘加载索引和元数据"""
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            print(f"--- [记忆库] 正在从 {self.index_path} 加载索引... ---")
            self.index = faiss.read_index(self.index_path)
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.metadata_store = json.load(f)
        else:
            print("--- [记忆库] 未找到现有索引，将创建新索引。 ---")
            self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.dimension))

    def _save(self):
        """保存索引和元数据到磁盘"""
        with _mem_instance_lock:
            print(f"--- [记忆库] 正在保存索引到 {self.index_path}... ---")
            faiss.write_index(self.index, self.index_path)
            with open(self.meta_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata_store, f, ensure_ascii=False, indent=2)

    def add(self, text: str, metadata: dict = None):
        """向记忆中添加信息"""
        with _mem_instance_lock:
            embedding = self.embedder.encode([text]).astype('float32')
            new_id = self.index.ntotal
            self.index.add_with_ids(embedding, np.array([new_id]))
            self.metadata_store.append({
                "id": new_id,
                "text": text,
                "metadata": metadata or {}
            })
            self._save()

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """从记忆中搜索信息"""
        if self.index.ntotal == 0:
            return []

        query_embedding = self.embedder.encode([query]).astype('float32')
        with _mem_instance_lock:
            distances, ids = self.index.search(query_embedding, limit)

        results = []
        if ids[0] is not None:
            for i, doc_id in enumerate(ids[0]):
                if doc_id != -1:
                    # 使用列表推导式查找，更高效
                    entry = next((item for item in self.metadata_store if item["id"] == doc_id), None)
                    if entry:
                        results.append({
                            "text": entry["text"],
                            "metadata": entry["metadata"],
                            "distance": float(distances[0][i])
                        })
        return results


# 修复：重构为工厂函数，接收配置对象以确保一致性
def get_memory_manager(config: Configuration) -> Optional[FaissMemoryManager]:
    """
    获取记忆管理器的单例。
    简化注释：获取记忆管理器实例
    """
    if not config.enable_mem0:
        return None

    index_path = config.mem0_index_path

    with _mem_instance_lock:
        if index_path in _mem_instance_cache:
            return _mem_instance_cache[index_path]

        print(f"--- [Mem0] 正在初始化记忆库，路径: {index_path} ---")
        # 确保目录存在
        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        instance = FaissMemoryManager(index_path=index_path)
        _mem_instance_cache[index_path] = instance
        return instance


def add_to_memory(text: str, metadata: dict = None, *, config: Configuration):
    """
    向长期记忆中添加信息。
    简化注释：添加记忆
    """
    if not text:
        return

    manager = get_memory_manager(config)
    if manager:
        try:
            manager.add(text, metadata=metadata)
            print(f"--- [记忆库] 已添加新记忆: {text[:50]}... ---")
        except Exception as e:
            print(f"--- [记忆库] 添加记忆时发生错误: {e} ---")


def search_in_memory(query: str, top_k: int = 3, *, config: Configuration) -> List[Dict[str, Any]]:
    """
    从长期记忆中搜索信息。
    简化注释：搜索记忆
    """
    manager = get_memory_manager(config)
    if manager:
        try:
            results = manager.search(query, limit=top_k)
            print(f"--- [记忆库] 从记忆中检索到 {len(results)} 条相关信息 ---")
            return results
        except Exception as e:
            print(f"--- [记忆库] 搜索记忆时发生错误: {e} ---")
    return []