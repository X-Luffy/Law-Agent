"""ChromaDB向量数据库实现"""
from typing import List, Dict, Any, Optional
import os
from .vector_store_interface import VectorStoreInterface

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class ChromaVectorStore(VectorStoreInterface):
    """ChromaDB向量数据库实现"""
    
    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = "default"):
        """
        初始化ChromaDB向量存储
        
        Args:
            persist_directory: 持久化目录（如果为None，则使用内存模式）
            collection_name: 集合名称
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is not installed. Please install it with: pip install chromadb")
        
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client: Optional[chromadb.ClientAPI] = None
        self.collection: Optional[chromadb.Collection] = None
        self.dimension: Optional[int] = None
    
    def initialize(self, collection_name: str, dimension: int):
        """
        初始化向量数据库
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
        """
        self.collection_name = collection_name
        self.dimension = dimension
        
        # 初始化ChromaDB客户端
        if self.persist_directory:
            # 持久化模式
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        else:
            # 内存模式
            self.client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False)
            )
        
        # 获取或创建集合
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            # 集合不存在，创建新集合
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"dimension": dimension}
            )
    
    def add(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        id: Optional[str] = None
    ) -> str:
        """
        添加向量到数据库
        
        Args:
            content: 文本内容
            embedding: 向量
            metadata: 元数据
            id: 可选的ID（如果不提供则自动生成）
            
        Returns:
            存储的ID
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        if id is None:
            import uuid
            id = str(uuid.uuid4())
        
        # 验证embedding维度
        if self.dimension and len(embedding) != self.dimension:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
        
        # 添加向量到ChromaDB
        self.collection.add(
            ids=[id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )
        
        return id
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_embedding: 查询向量
            top_k: 返回top-k个结果
            filter_metadata: 元数据过滤条件
            
        Returns:
            搜索结果列表，每个结果包含content, metadata, score, id等
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        # 构建查询where条件（ChromaDB的过滤语法）
        where = None
        if filter_metadata:
            where = filter_metadata
        
        # 在ChromaDB中搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )
        
        # 格式化结果
        formatted_results = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - results["distances"][0][i] if results["distances"] else 0.0  # 距离转相似度
                })
        
        return formatted_results
    
    def delete(self, id: str) -> bool:
        """
        删除向量
        
        Args:
            id: 向量ID
            
        Returns:
            是否删除成功
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        try:
            self.collection.delete(ids=[id])
            return True
        except Exception:
            return False
    
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            id: 向量ID
            
        Returns:
            向量信息（包含content, embedding, metadata等），如果不存在返回None
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        try:
            results = self.collection.get(ids=[id], include=["embeddings", "documents", "metadatas"])
            if results["ids"] and len(results["ids"]) > 0:
                return {
                    "id": results["ids"][0],
                    "content": results["documents"][0] if results["documents"] else "",
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                    "embedding": results["embeddings"][0] if results["embeddings"] else []
                }
        except Exception:
            pass
        
        return None
    
    def update(
        self,
        id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新向量
        
        Args:
            id: 向量ID
            content: 新的文本内容（可选）
            embedding: 新的向量（可选）
            metadata: 新的元数据（可选）
            
        Returns:
            是否更新成功
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        try:
            # 获取现有数据
            existing = self.get(id)
            if existing is None:
                return False
            
            # 合并更新
            new_content = content if content is not None else existing["content"]
            new_embedding = embedding if embedding is not None else existing.get("embedding", [])
            new_metadata = existing["metadata"].copy()
            if metadata is not None:
                new_metadata.update(metadata)
            
            # 删除旧数据
            self.collection.delete(ids=[id])
            
            # 添加新数据
            self.collection.add(
                ids=[id],
                embeddings=[new_embedding],
                documents=[new_content],
                metadatas=[new_metadata]
            )
            
            return True
        except Exception:
            return False
    
    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有向量
        
        Args:
            limit: 限制返回数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            向量列表
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        # 构建查询where条件
        where = None
        if filter_metadata:
            where = filter_metadata
        
        # 获取所有数据
        results = self.collection.get(
            where=where,
            limit=limit,
            include=["embeddings", "documents", "metadatas"]
        )
        
        # 格式化结果
        formatted_results = []
        if results["ids"]:
            for i in range(len(results["ids"])):
                formatted_results.append({
                    "id": results["ids"][i],
                    "content": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    "embedding": results["embeddings"][i] if results["embeddings"] else []
                })
        
        return formatted_results
    
    def count(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        获取向量数量
        
        Args:
            filter_metadata: 元数据过滤条件
            
        Returns:
            向量数量
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        # 构建查询where条件
        where = None
        if filter_metadata:
            where = filter_metadata
        
        # 获取所有ID（用于计数）
        results = self.collection.get(where=where)
        return len(results["ids"]) if results["ids"] else 0
    
    def clear(self) -> bool:
        """
        清空所有向量
        
        Returns:
            是否清空成功
        """
        if self.collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        
        try:
            # 获取所有ID
            results = self.collection.get()
            if results["ids"]:
                # 删除所有向量
                self.collection.delete(ids=results["ids"])
            return True
        except Exception:
            return False

