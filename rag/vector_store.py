"""向量存储模块（使用memory模块的统一接口）"""
from typing import List, Dict, Any, Optional
from ..config.config import Config
from ..memory.vector_db import VectorDatabase


class VectorStore:
    """向量存储，用于存储和检索文档向量（使用memory模块的统一接口）"""
    
    def __init__(self, config: Config):
        """
        初始化向量存储
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.collection_name = "legal_documents"  # 法律文档集合
        
        # 使用memory模块的向量数据库
        self.vector_db = VectorDatabase(config)
        
        # 初始化向量存储
        self._initialize_store()
    
    def _initialize_store(self):
        """初始化向量存储"""
        # 向量数据库已经在VectorDatabase中初始化
        pass
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        添加文档到向量存储
        
        Args:
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表
        """
        if metadatas is None:
            metadatas = [{"type": "legal_document"} for _ in documents]
        
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # 添加文档到向量数据库
        for doc, metadata, doc_id in zip(documents, metadatas, ids):
            # 添加类型标识
            metadata["type"] = "legal_document"
            self.vector_db.add_memory(
                content=doc,
                metadata=metadata,
                id=doc_id
            )
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            filter_metadata: 元数据过滤条件
            
        Returns:
            相关文档列表，每个文档包含content, metadata, score等
        """
        # 合并过滤条件
        if filter_metadata is None:
            filter_metadata = {"type": "legal_document"}
        else:
            filter_metadata["type"] = "legal_document"
        
        # 使用向量数据库搜索
        results = self.vector_db.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        return results
    
    def delete_documents(self, ids: List[str]):
        """
        删除文档
        
        Args:
            ids: 文档ID列表
        """
        # TODO: 实现文档删除逻辑
        pass
    
    def get_all_documents(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有文档
        
        Args:
            limit: 限制返回数量
            
        Returns:
            文档列表
        """
        # TODO: 实现获取所有文档逻辑
        pass

