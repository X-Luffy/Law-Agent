"""长期记忆向量数据库（使用统一接口）"""
from typing import List, Dict, Any, Optional
import uuid
from .vector_store_interface import VectorStoreInterface
# 处理相对导入问题
try:
    from ..config.config import Config
    from ..models.model import EmbeddingModel
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config
    from models.model import EmbeddingModel


class VectorDatabase:
    """长期记忆向量数据库，使用向量检索存储和检索历史对话"""
    
    def __init__(self, config: Config, vector_store: Optional[VectorStoreInterface] = None):
        """
        初始化向量数据库
        
        Args:
            config: 系统配置
            vector_store: 向量存储接口（如果为None，则使用默认实现）
        """
        self.config = config
        self.db_path = config.vector_db_path
        self.collection_name = config.vector_db_collection
        
        # 初始化embedding模型
        self.embedding_model = EmbeddingModel(config)
        
        # 自动检测embedding维度（如果配置为0或需要检测）
        if config.embedding_dim == 0 or config.embedding_dim is None:
            # 使用一个测试文本检测维度
            try:
                test_embedding = self.embedding_model.encode("test")
                actual_dim = len(test_embedding)
                config.embedding_dim = actual_dim
                print(f"自动检测到embedding维度: {actual_dim}")
            except Exception as e:
                print(f"Warning: 无法自动检测embedding维度: {e}")
                # 使用默认值
                config.embedding_dim = config.embedding_dim or 1024
        
        # 初始化向量存储接口
        if vector_store is None:
            # 使用默认的向量存储实现（需要后续实现）
            self.vector_store = self._create_default_vector_store()
        else:
            self.vector_store = vector_store
        
        # 初始化向量数据库
        self._initialize_db()
    
    def _create_default_vector_store(self) -> VectorStoreInterface:
        """
        创建默认的向量存储实现
        
        Returns:
            向量存储接口实例
        """
        # 优先使用ChromaDB（如果可用）
        try:
            from .vector_store_chroma import ChromaVectorStore
            return ChromaVectorStore(
                persist_directory=self.db_path,
                collection_name=self.collection_name
            )
        except ImportError:
            # 如果ChromaDB不可用，使用占位符实现
            print("Warning: ChromaDB not available, using placeholder implementation")
            from .vector_store_placeholder import VectorStorePlaceholder
            return VectorStorePlaceholder()
    
    def _initialize_db(self):
        """初始化向量数据库连接"""
        try:
            self.vector_store.initialize(
                collection_name=self.collection_name,
                dimension=self.embedding_model.get_dimension()
            )
        except Exception as e:
            print(f"Warning: Failed to initialize vector store: {e}")
    
    def add_memory(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        id: Optional[str] = None
    ) -> str:
        """
        添加记忆到向量数据库
        
        Args:
            content: 记忆内容（对话内容）
            metadata: 元数据（session_id, intent, timestamp等）
            embedding: 可选的预计算embedding
            id: 可选的ID
            
        Returns:
            存储的ID
        """
        # 如果没有提供embedding，使用embedding模型生成
        if embedding is None:
            try:
                embedding = self.embedding_model.encode(content)
            except Exception as e:
                raise RuntimeError(f"Failed to generate embedding: {e}")
        
        # 如果没有提供ID，自动生成
        if id is None:
            id = str(uuid.uuid4())
        
        # 添加时间戳
        import datetime
        metadata["timestamp"] = datetime.datetime.now().isoformat()
        metadata["id"] = id
        
        # 存储到向量数据库
        try:
            stored_id = self.vector_store.add(
                content=content,
                embedding=embedding,
                metadata=metadata,
                id=id
            )
            return stored_id
        except Exception as e:
            raise RuntimeError(f"Failed to add memory to vector store: {e}")
    
    def search(
        self, 
        query: str, 
        top_k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回top-k结果
            filter_metadata: 元数据过滤条件
            
        Returns:
            相关记忆列表，每个记忆包含content, metadata, score等
        """
        if top_k is None:
            top_k = self.config.long_term_memory_top_k
        
        # 将query转换为embedding
        try:
            query_embedding = self.embedding_model.encode(query)
        except Exception as e:
            raise RuntimeError(f"Failed to encode query: {e}")
        
        # 在向量数据库中搜索相似向量
        try:
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            return results
        except Exception as e:
            raise RuntimeError(f"Failed to search vector store: {e}")
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        try:
            return self.vector_store.delete(memory_id)
        except Exception as e:
            print(f"Warning: Failed to delete memory: {e}")
            return False
    
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆信息，如果不存在返回None
        """
        try:
            return self.vector_store.get(memory_id)
        except Exception as e:
            print(f"Warning: Failed to get memory: {e}")
            return None
    
    def get_all_memories(
        self, 
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有记忆
        
        Args:
            limit: 限制返回数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            记忆列表
        """
        try:
            return self.vector_store.get_all(limit=limit, filter_metadata=filter_metadata)
        except Exception as e:
            print(f"Warning: Failed to get all memories: {e}")
            return []
    
    def count_memories(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        获取记忆数量
        
        Args:
            filter_metadata: 元数据过滤条件
            
        Returns:
            记忆数量
        """
        try:
            return self.vector_store.count(filter_metadata=filter_metadata)
        except Exception as e:
            print(f"Warning: Failed to count memories: {e}")
            return 0
    
    def clear_all_memories(self) -> bool:
        """
        清空所有记忆
        
        Returns:
            是否清空成功
        """
        try:
            return self.vector_store.clear()
        except Exception as e:
            print(f"Warning: Failed to clear memories: {e}")
            return False
    
    def add_tool_description(
        self,
        tool_name: str,
        description: str,
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        添加工具描述到向量数据库（用于工具选择）
        
        Args:
            tool_name: 工具名称
            description: 工具描述
            embedding: 可选的预计算embedding
            
        Returns:
            存储的ID
        """
        metadata = {
            "type": "tool_description",
            "tool_name": tool_name
        }
        return self.add_memory(
            content=description,
            metadata=metadata,
            embedding=embedding
        )
    
    def search_tool_descriptions(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相关工具描述
        
        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            
        Returns:
            相关工具描述列表
        """
        filter_metadata = {"type": "tool_description"}
        return self.search(query, top_k=top_k, filter_metadata=filter_metadata)
    
    def add_refined_context(
        self,
        summary: str,
        key_points: List[str],
        important_info: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        添加精炼后的上下文到向量数据库
        
        Args:
            summary: 摘要
            key_points: 关键点列表
            important_info: 重要信息
            embedding: 可选的预计算embedding
            
        Returns:
            存储的ID
        """
        # 合并内容
        content = f"Summary: {summary}\n\nKey Points:\n" + "\n".join(f"- {point}" for point in key_points)
        
        metadata = {
            "type": "refined_context",
            "key_points": key_points,
            "important_info": important_info
        }
        
        return self.add_memory(
            content=content,
            metadata=metadata,
            embedding=embedding
        )
