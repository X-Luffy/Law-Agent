"""向量数据库接口（抽象基类）"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorStoreInterface(ABC):
    """向量数据库接口，定义统一的向量存储和检索接口"""
    
    @abstractmethod
    def initialize(self, collection_name: str, dimension: int):
        """
        初始化向量数据库
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        删除向量
        
        Args:
            id: 向量ID
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            id: 向量ID
            
        Returns:
            向量信息（包含content, embedding, metadata等），如果不存在返回None
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def count(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        获取向量数量
        
        Args:
            filter_metadata: 元数据过滤条件
            
        Returns:
            向量数量
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        清空所有向量
        
        Returns:
            是否清空成功
        """
        pass

