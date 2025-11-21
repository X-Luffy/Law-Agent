"""RAG检索器"""
from typing import List, Dict, Any, Optional
from .vector_store import VectorStore
from ..embedding.model import EmbeddingModel
from ..config.config import Config


class RAGRetriever:
    """RAG检索器，用于从专业数据库中检索相关信息"""
    
    def __init__(self, config: Config):
        """
        初始化RAG检索器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.vector_store = VectorStore(config)
        self.embedding_model = EmbeddingModel(config)
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关信息
        
        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            filter_metadata: 元数据过滤条件（如法律类型、日期等）
            
        Returns:
            相关文档列表，每个文档包含content, metadata, score等
        """
        # 使用向量存储进行检索
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        return results
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        添加文档到RAG系统
        
        Args:
            documents: 文档列表
            metadatas: 元数据列表（如法律类型、章节、日期等）
            ids: 文档ID列表
        """
        self.vector_store.add_documents(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        对检索结果进行重排序
        
        Args:
            query: 查询文本
            documents: 检索到的文档列表
            top_k: 返回top-k个结果
            
        Returns:
            重排序后的文档列表
        """
        # TODO: 实现重排序逻辑
        # 可以使用cross-encoder或其他重排序模型
        # 这里先返回原始结果
        if top_k:
            return documents[:top_k]
        return documents

