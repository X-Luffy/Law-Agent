"""工具选择器"""
from typing import List, Dict, Any, Optional
import numpy as np
from .model import EmbeddingModel
from ..config.config import Config


class ToolSelector:
    """工具选择器，使用embedding进行工具选择"""
    
    def __init__(self, config: Config):
        """
        初始化工具选择器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.embedding_model = EmbeddingModel(config)
        
        # 工具描述和对应的embedding
        self.tool_descriptions: Dict[str, str] = {}
        self.tool_embeddings: Dict[str, List[float]] = {}
        
        # 相似度阈值（可选）
        self.similarity_threshold: float = 0.5
    
    def embed_tool_descriptions(self, tool_descriptions: Dict[str, str]):
        """
        嵌入工具描述
        
        Args:
            tool_descriptions: 工具名称到描述的字典
        """
        self.tool_descriptions = tool_descriptions
        
        # 为每个工具描述生成embedding
        try:
            # 批量编码所有工具描述
            descriptions = list(tool_descriptions.values())
            embeddings = self.embedding_model.encode(descriptions)
            
            # 存储每个工具的embedding
            for i, (tool_name, description) in enumerate(tool_descriptions.items()):
                if isinstance(embeddings, list) and len(embeddings) > i:
                    if isinstance(embeddings[i], list):
                        self.tool_embeddings[tool_name] = embeddings[i]
                    else:
                        # 如果是单个向量，直接存储
                        self.tool_embeddings[tool_name] = embeddings
                else:
                    # 如果批量编码失败，逐个编码
                    embedding = self.embedding_model.encode(description)
                    self.tool_embeddings[tool_name] = embedding
        
        except Exception as e:
            # 如果批量编码失败，逐个编码
            for tool_name, description in tool_descriptions.items():
                try:
                    embedding = self.embedding_model.encode(description)
                    self.tool_embeddings[tool_name] = embedding
                except Exception as e2:
                    print(f"Warning: Failed to encode tool '{tool_name}': {e2}")
    
    def select_tools(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        top_k: int = 3,
        similarity_threshold: Optional[float] = None
    ) -> List[str]:
        """
        选择相关工具（使用embedding进行相似度计算）
        
        Args:
            user_input: 用户输入
            context: 上下文信息
            top_k: 返回top-k个工具
            similarity_threshold: 相似度阈值（可选）
            
        Returns:
            选中的工具名称列表
        """
        if not self.tool_embeddings:
            return []
        
        # 构建查询文本（用户输入 + 上下文）
        query_text = user_input
        
        # 从上下文中提取相关信息
        if context:
            # 可以添加上下文信息到查询中
            recent_messages = context.get("messages", [])
            if recent_messages:
                # 提取最近的用户消息
                for msg in reversed(recent_messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        query_text = f"{msg.get('content', '')} {query_text}"
                        break
        
        # 将用户查询转换为embedding
        try:
            query_embedding = self.embedding_model.encode(query_text)
        except Exception as e:
            print(f"Warning: Failed to encode query: {e}")
            return []
        
        # 计算与各个工具描述的相似度（余弦相似度）
        similarities = []
        for tool_name, tool_embedding in self.tool_embeddings.items():
            similarity = self._compute_similarity(query_embedding, tool_embedding)
            similarities.append((tool_name, similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 应用相似度阈值
        threshold = similarity_threshold or self.similarity_threshold
        filtered_similarities = [
            (tool_name, sim) for tool_name, sim in similarities
            if sim >= threshold
        ]
        
        # 选择top-k个工具
        selected_tools = [
            tool_name for tool_name, _ in filtered_similarities[:top_k]
        ]
        
        return selected_tools
    
    def _compute_similarity(
        self, 
        query_embedding: List[float], 
        tool_embedding: List[float]
    ) -> float:
        """
        计算相似度（余弦相似度）
        
        Args:
            query_embedding: 查询向量
            tool_embedding: 工具向量
            
        Returns:
            相似度分数（0-1之间）
        """
        try:
            # 转换为numpy数组
            query_vec = np.array(query_embedding)
            tool_vec = np.array(tool_embedding)
            
            # 计算余弦相似度
            dot_product = np.dot(query_vec, tool_vec)
            norm_query = np.linalg.norm(query_vec)
            norm_tool = np.linalg.norm(tool_vec)
            
            if norm_query == 0 or norm_tool == 0:
                return 0.0
            
            similarity = dot_product / (norm_query * norm_tool)
            
            # 确保相似度在0-1之间
            return max(0.0, min(1.0, similarity))
        
        except Exception as e:
            print(f"Warning: Failed to compute similarity: {e}")
            return 0.0
    
    def get_tool_similarities(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """
        获取所有工具的相似度分数
        
        Args:
            user_input: 用户输入
            context: 上下文信息（可选）
            
        Returns:
            (工具名称, 相似度分数) 的列表，按相似度降序排列
        """
        if not self.tool_embeddings:
            return []
        
        # 构建查询文本
        query_text = user_input
        if context:
            recent_messages = context.get("messages", [])
            if recent_messages:
                for msg in reversed(recent_messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        query_text = f"{msg.get('content', '')} {query_text}"
                        break
        
        # 将查询转换为embedding
        try:
            query_embedding = self.embedding_model.encode(query_text)
        except Exception as e:
            print(f"Warning: Failed to encode query: {e}")
            return []
        
        # 计算所有工具的相似度
        similarities = []
        for tool_name, tool_embedding in self.tool_embeddings.items():
            similarity = self._compute_similarity(query_embedding, tool_embedding)
            similarities.append((tool_name, similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
    
    def set_similarity_threshold(self, threshold: float):
        """
        设置相似度阈值
        
        Args:
            threshold: 相似度阈值（0-1之间）
        """
        self.similarity_threshold = max(0.0, min(1.0, threshold))
