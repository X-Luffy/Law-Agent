"""向量数据库占位符实现（用于测试和开发）"""
from typing import List, Dict, Any, Optional
from .vector_store_interface import VectorStoreInterface
import numpy as np


class VectorStorePlaceholder(VectorStoreInterface):
    """向量数据库占位符实现，使用内存存储（用于测试和开发）"""
    
    def __init__(self):
        """初始化占位符实现"""
        self.collection_name: Optional[str] = None
        self.dimension: Optional[int] = None
        self.storage: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
    
    def initialize(self, collection_name: str, dimension: int):
        """初始化向量数据库"""
        self.collection_name = collection_name
        self.dimension = dimension
        self.storage.clear()
        self.embeddings.clear()
    
    def add(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        id: Optional[str] = None
    ) -> str:
        """添加向量到数据库"""
        if id is None:
            import uuid
            id = str(uuid.uuid4())
        
        # 验证embedding维度
        if self.dimension and len(embedding) != self.dimension:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
        
        # 存储数据
        self.storage[id] = {
            "content": content,
            "metadata": metadata,
            "id": id
        }
        self.embeddings[id] = embedding
        
        return id
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        if not self.embeddings:
            return []
        
        # 计算相似度
        similarities = []
        for id, embedding in self.embeddings.items():
            # 应用元数据过滤
            if filter_metadata:
                metadata = self.storage[id].get("metadata", {})
                if not self._match_filter(metadata, filter_metadata):
                    continue
            
            # 计算余弦相似度
            similarity = self._cosine_similarity(query_embedding, embedding)
            similarities.append((id, similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top-k结果
        results = []
        for id, score in similarities[:top_k]:
            item = self.storage[id].copy()
            item["score"] = score
            results.append(item)
        
        return results
    
    def delete(self, id: str) -> bool:
        """删除向量"""
        if id in self.storage:
            del self.storage[id]
            del self.embeddings[id]
            return True
        return False
    
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """获取指定ID的向量"""
        if id in self.storage:
            item = self.storage[id].copy()
            item["embedding"] = self.embeddings[id]
            return item
        return None
    
    def update(
        self,
        id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新向量"""
        if id not in self.storage:
            return False
        
        if content is not None:
            self.storage[id]["content"] = content
        
        if embedding is not None:
            if self.dimension and len(embedding) != self.dimension:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
            self.embeddings[id] = embedding
        
        if metadata is not None:
            self.storage[id]["metadata"].update(metadata)
        
        return True
    
    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """获取所有向量"""
        results = []
        for id, item in self.storage.items():
            # 应用元数据过滤
            if filter_metadata:
                metadata = item.get("metadata", {})
                if not self._match_filter(metadata, filter_metadata):
                    continue
            
            result = item.copy()
            result["embedding"] = self.embeddings[id]
            results.append(result)
            
            if limit and len(results) >= limit:
                break
        
        return results
    
    def count(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """获取向量数量"""
        if not filter_metadata:
            return len(self.storage)
        
        count = 0
        for item in self.storage.values():
            metadata = item.get("metadata", {})
            if self._match_filter(metadata, filter_metadata):
                count += 1
        return count
    
    def clear(self) -> bool:
        """清空所有向量"""
        self.storage.clear()
        self.embeddings.clear()
        return True
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _match_filter(self, metadata: Dict[str, Any], filter_metadata: Dict[str, Any]) -> bool:
        """检查元数据是否匹配过滤条件"""
        for key, value in filter_metadata.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True

