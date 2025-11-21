"""上下文精炼模块，使用embedding进行精炼"""
from typing import List, Dict, Any
import numpy as np
from ..config.config import Config
from ..embedding.model import EmbeddingModel
from ..llm.llm import LLM


class ContextRefiner:
    """上下文精炼模块，将往期对话压缩为摘要（使用embedding进行聚类和摘要）"""
    
    def __init__(self, config: Config):
        """
        初始化上下文精炼器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.embedding_model = EmbeddingModel(config)
        self.llm = LLM(config)
    
    def refine(
        self, 
        old_messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        精炼往期对话，生成摘要（使用embedding进行聚类和摘要）
        
        Args:
            old_messages: 往期对话消息列表
            
        Returns:
            精炼后的上下文，包含summary, key_points, important_info等
        """
        if not old_messages:
            return {
                "summary": "",
                "key_points": [],
                "important_info": {}
            }
        
        # 1. 使用embedding对消息进行聚类，提取关键信息点
        key_points = self._extract_key_points_with_embedding(old_messages)
        
        # 2. 使用LLM生成对话摘要
        summary = self._generate_summary(old_messages, key_points)
        
        # 3. 提取重要的用户意图和决策
        important_info = self._extract_important_info(old_messages)
        
        return {
            "summary": summary,
            "key_points": key_points,
            "important_info": important_info,
            "message_count": len(old_messages)
        }
    
    def _extract_key_points_with_embedding(
        self, 
        messages: List[Dict[str, Any]],
        max_points: int = 5
    ) -> List[str]:
        """
        使用embedding提取关键信息点（通过聚类相似消息）
        
        Args:
            messages: 消息列表
            max_points: 最大关键点数量
            
        Returns:
            关键信息点列表
        """
        if not messages:
            return []
        
        # 提取消息内容
        message_contents = []
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                role = msg.get("role", "")
                if content and role in ["user", "assistant"]:
                    message_contents.append(f"{role}: {content}")
            else:
                # 如果是Message对象
                if hasattr(msg, "content") and msg.content:
                    role = getattr(msg, "role", "")
                    message_contents.append(f"{role}: {msg.content}")
        
        if not message_contents:
            return []
        
        # 使用embedding对消息进行编码
        try:
            embeddings = self.embedding_model.encode(message_contents)
            
            # 简单的聚类：找到最不同的消息
            if len(embeddings) <= max_points:
                # 如果消息数量少于max_points，直接返回所有消息的摘要
                return [self._summarize_message(msg) for msg in message_contents[:max_points]]
            
            # 使用简单的聚类方法：选择最不同的消息
            # 计算消息之间的相似度，选择最不相似的消息作为关键点
            key_indices = self._select_diverse_messages(embeddings, max_points)
            
            # 提取关键点
            key_points = [self._summarize_message(message_contents[i]) for i in key_indices]
            
            return key_points
        
        except Exception as e:
            # 如果embedding失败，使用简单的文本摘要
            return [self._summarize_message(msg) for msg in message_contents[:max_points]]
    
    def _select_diverse_messages(
        self,
        embeddings: List[List[float]],
        max_points: int
    ) -> List[int]:
        """
        选择最不同的消息（使用embedding相似度）
        
        Args:
            embeddings: embedding向量列表
            max_points: 最大选择数量
            
        Returns:
            选中的消息索引列表
        """
        if len(embeddings) <= max_points:
            return list(range(len(embeddings)))
        
        # 转换为numpy数组
        embeddings_array = np.array(embeddings)
        
        # 选择第一个消息
        selected_indices = [0]
        
        # 逐步选择最不同的消息
        for _ in range(max_points - 1):
            if len(selected_indices) >= len(embeddings):
                break
            
            # 计算已选择消息的embedding
            selected_embeddings = embeddings_array[selected_indices]
            
            # 计算每个未选择消息与已选择消息的最小相似度
            min_similarities = []
            for i in range(len(embeddings)):
                if i in selected_indices:
                    continue
                
                # 计算与已选择消息的最大相似度（余弦相似度）
                similarities = []
                for selected_emb in selected_embeddings:
                    similarity = self._cosine_similarity(embeddings[i], selected_emb)
                    similarities.append(similarity)
                
                # 选择最小相似度（最不同）
                min_similarities.append((i, min(similarities)))
            
            if not min_similarities:
                break
            
            # 选择最小相似度最大的消息（最不同）
            min_similarities.sort(key=lambda x: x[1], reverse=True)
            selected_indices.append(min_similarities[0][0])
        
        return selected_indices
    
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
    
    def _summarize_message(self, message: str, max_length: int = 100) -> str:
        """
        摘要单个消息
        
        Args:
            message: 消息内容
            max_length: 最大长度
            
        Returns:
            摘要后的消息
        """
        if len(message) <= max_length:
            return message
        
        # 简单的截断摘要
        return message[:max_length] + "..."
    
    def _generate_summary(
        self, 
        messages: List[Dict[str, Any]],
        key_points: List[str]
    ) -> str:
        """
        使用LLM生成对话摘要
        
        Args:
            messages: 消息列表
            key_points: 关键信息点列表
            
        Returns:
            对话摘要文本
        """
        if not messages:
            return ""
        
        # 构建消息文本
        conversation_text = ""
        for msg in messages[-10:]:  # 只使用最近10条消息生成摘要
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    conversation_text += f"{role}: {content}\n"
            else:
                if hasattr(msg, "content") and msg.content:
                    role = getattr(msg, "role", "")
                    conversation_text += f"{role}: {msg.content}\n"
        
        # 构建prompt
        prompt = f"""请对以下对话进行摘要，保留重要信息：

对话内容：
{conversation_text}

关键信息点：
{chr(10).join(f"- {point}" for point in key_points)}

请生成一个简洁的摘要，包含：
1. 对话的主要主题
2. 用户的主要意图
3. 重要的决策或结论

摘要："""
        
        try:
            # 使用LLM生成摘要
            summary = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 使用较低温度以获得更稳定的摘要
                max_tokens=500
            )
            return summary
        except Exception as e:
            # 如果LLM调用失败，返回简单的文本摘要
            return f"对话摘要：共{len(messages)}条消息，主要讨论{key_points[0] if key_points else '未知主题'}"
    
    def _extract_important_info(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        提取重要的用户意图和决策
        
        Args:
            messages: 消息列表
            
        Returns:
            重要信息字典
        """
        important_info = {
            "user_intents": [],
            "decisions": [],
            "key_entities": []
        }
        
        # 简单的提取逻辑（可以后续使用NER或LLM增强）
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user" and content:
                    # 提取用户意图（简单规则）
                    if "?" in content or "？" in content:
                        important_info["user_intents"].append(content[:100])
            else:
                if hasattr(msg, "role") and msg.role == "user":
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        if "?" in content or "？" in content:
                            important_info["user_intents"].append(content[:100])
        
        return important_info
