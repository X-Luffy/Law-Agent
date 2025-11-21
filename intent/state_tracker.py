"""状态追踪器"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..config.config import Config
from ..llm.llm import LLM


class StateTracker:
    """状态追踪器，维护当前意图和已有信息"""
    
    def __init__(self, config: Config):
        """
        初始化状态追踪器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.llm = LLM(config)
        
        # 内部状态存储
        self.state_storage: Dict[str, Any] = {
            "current_intent": None,
            "intent_history": [],
            "collected_info": {},
            "conversation_state": "idle",  # idle, waiting_input, processing, completed
            "key_entities": [],
            "pending_questions": []
        }
    
    def update_state(
        self, 
        agent, 
        user_message: str, 
        intent: str
    ):
        """
        更新Agent状态
        
        Args:
            agent: Agent实例
            user_message: 用户消息
            intent: 识别出的意图
        """
        # 更新当前意图
        previous_intent = self.state_storage.get("current_intent")
        self.state_storage["current_intent"] = intent
        
        # 记录意图历史
        self.state_storage["intent_history"].append({
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
            "message": user_message[:100]  # 只保存前100字符
        })
        
        # 限制意图历史长度
        if len(self.state_storage["intent_history"]) > 20:
            self.state_storage["intent_history"] = self.state_storage["intent_history"][-20:]
        
        # 从用户消息中提取信息
        extracted_info = self._extract_info(user_message, intent)
        
        # 更新收集到的信息
        for key, value in extracted_info.items():
            self.state_storage["collected_info"][key] = value
        
        # 更新对话状态
        self._update_conversation_state(intent, previous_intent)
        
        # 提取关键实体
        entities = self._extract_entities(user_message, intent)
        if entities:
            self.state_storage["key_entities"].extend(entities)
            # 限制实体数量
            if len(self.state_storage["key_entities"]) > 50:
                self.state_storage["key_entities"] = self.state_storage["key_entities"][-50:]
    
    def _extract_info(
        self, 
        user_message: str, 
        intent: str
    ) -> Dict[str, Any]:
        """
        从用户消息中提取信息
        
        Args:
            user_message: 用户消息
            intent: 用户意图
            
        Returns:
            提取的信息字典
        """
        extracted = {}
        
        # 根据不同的意图类型提取相应信息
        if intent == "query":
            # 查询意图：提取查询主题、关键词等
            extracted["query_topic"] = self._extract_query_topic(user_message)
            extracted["keywords"] = self._extract_keywords(user_message)
        
        elif intent == "task":
            # 任务意图：提取任务类型、参数等
            extracted["task_type"] = self._extract_task_type(user_message)
            extracted["task_params"] = self._extract_task_params(user_message)
        
        elif intent == "clarification":
            # 澄清意图：提取需要澄清的内容
            extracted["clarification_target"] = self._extract_clarification_target(user_message)
        
        # 通用信息提取
        extracted["has_question"] = "?" in user_message or "？" in user_message
        extracted["has_request"] = any(word in user_message for word in ["请", "帮", "能否", "可以"])
        
        return extracted
    
    def _extract_query_topic(self, message: str) -> Optional[str]:
        """提取查询主题"""
        # 简单的关键词提取（可以后续使用NER增强）
        query_keywords = ["什么", "如何", "为什么", "哪里", "什么时候", "谁"]
        for keyword in query_keywords:
            if keyword in message:
                # 提取关键词后的内容作为主题
                idx = message.find(keyword)
                topic = message[idx:idx+50].strip()
                return topic
        return None
    
    def _extract_keywords(self, message: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取（可以后续使用更复杂的方法）
        keywords = []
        # 提取长度大于2的词
        words = message.split()
        for word in words:
            if len(word) >= 2:
                keywords.append(word)
        return keywords[:10]  # 最多返回10个关键词
    
    def _extract_task_type(self, message: str) -> Optional[str]:
        """提取任务类型"""
        task_keywords = {
            "计算": "calculation",
            "搜索": "search",
            "执行": "execution",
            "生成": "generation",
            "创建": "creation",
            "处理": "processing"
        }
        
        for keyword, task_type in task_keywords.items():
            if keyword in message:
                return task_type
        return None
    
    def _extract_task_params(self, message: str) -> Dict[str, Any]:
        """提取任务参数"""
        params = {}
        
        # 提取数字
        import re
        numbers = re.findall(r'\d+', message)
        if numbers:
            params["numbers"] = [int(n) for n in numbers]
        
        # 提取引号内的内容（可能是代码或命令）
        quoted = re.findall(r'["\']([^"\']+)["\']', message)
        if quoted:
            params["quoted_text"] = quoted
        
        return params
    
    def _extract_clarification_target(self, message: str) -> Optional[str]:
        """提取需要澄清的内容"""
        clarification_keywords = ["什么意思", "不明白", "不清楚", "解释", "说明"]
        for keyword in clarification_keywords:
            if keyword in message:
                return keyword
        return None
    
    def _extract_entities(
        self,
        message: str,
        intent: str
    ) -> List[Dict[str, Any]]:
        """
        提取关键实体
        
        Args:
            message: 用户消息
            intent: 用户意图
            
        Returns:
            实体列表
        """
        entities = []
        
        # 提取日期
        import re
        date_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 2024-01-01
            r'\d{1,2}月\d{1,2}日',  # 1月1日
        ]
        for pattern in date_patterns:
            dates = re.findall(pattern, message)
            for date in dates:
                entities.append({
                    "type": "date",
                    "value": date,
                    "text": date
                })
        
        # 提取数字
        numbers = re.findall(r'\d+', message)
        for number in numbers:
            if len(number) > 1:  # 只提取长度大于1的数字
                entities.append({
                    "type": "number",
                    "value": int(number),
                    "text": number
                })
        
        # 提取法律相关实体（简单规则）
        law_keywords = ["法", "条例", "规定", "条款", "合同", "协议", "诉讼", "律师", "法院"]
        for keyword in law_keywords:
            if keyword in message:
                # 提取包含关键词的短语
                idx = message.find(keyword)
                start = max(0, idx - 10)
                end = min(len(message), idx + 10)
                phrase = message[start:end]
                entities.append({
                    "type": "law_entity",
                    "value": keyword,
                    "text": phrase
                })
        
        return entities
    
    def _update_conversation_state(
        self,
        current_intent: str,
        previous_intent: Optional[str]
    ):
        """更新对话状态"""
        if current_intent == "greeting":
            self.state_storage["conversation_state"] = "idle"
        elif current_intent == "goodbye":
            self.state_storage["conversation_state"] = "completed"
        elif current_intent == "clarification":
            self.state_storage["conversation_state"] = "waiting_input"
        elif current_intent == "task":
            self.state_storage["conversation_state"] = "processing"
        elif current_intent == "query":
            self.state_storage["conversation_state"] = "processing"
        else:
            self.state_storage["conversation_state"] = "idle"
    
    def get_state_summary(self, agent) -> Dict[str, Any]:
        """
        获取状态摘要
        
        Args:
            agent: Agent实例
            
        Returns:
            状态摘要
        """
        return {
            "current_intent": self.state_storage.get("current_intent"),
            "conversation_state": self.state_storage.get("conversation_state"),
            "intent_history_count": len(self.state_storage.get("intent_history", [])),
            "collected_info_keys": list(self.state_storage.get("collected_info", {}).keys()),
            "key_entities_count": len(self.state_storage.get("key_entities", [])),
            "recent_intents": [
                item["intent"] for item in self.state_storage.get("intent_history", [])[-5:]
            ]
        }
    
    def get_current_intent(self) -> Optional[str]:
        """获取当前意图"""
        return self.state_storage.get("current_intent")
    
    def get_collected_info(self) -> Dict[str, Any]:
        """获取收集到的信息"""
        return self.state_storage.get("collected_info", {}).copy()
    
    def get_key_entities(self) -> List[Dict[str, Any]]:
        """获取关键实体"""
        return self.state_storage.get("key_entities", []).copy()
    
    def clear_state(self):
        """清空状态"""
        self.state_storage = {
            "current_intent": None,
            "intent_history": [],
            "collected_info": {},
            "conversation_state": "idle",
            "key_entities": [],
            "pending_questions": []
        }
    
    def add_pending_question(self, question: str):
        """添加待回答问题"""
        self.state_storage["pending_questions"].append({
            "question": question,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_pending_questions(self) -> List[Dict[str, Any]]:
        """获取待回答问题"""
        return self.state_storage.get("pending_questions", []).copy()
    
    def clear_pending_questions(self):
        """清空待回答问题"""
        self.state_storage["pending_questions"] = []
