"""意图识别器"""
from typing import Dict, Any, Optional, List
from ..config.config import Config
from ..schema import AgentState
from ..llm.llm import LLM


class IntentRecognizer:
    """用户意图识别器，使用LLM和规则匹配进行意图识别"""
    
    # 意图类型定义
    INTENT_QUERY = "query"  # 查询信息
    INTENT_TASK = "task"  # 执行任务
    INTENT_CLARIFICATION = "clarification"  # 澄清问题
    INTENT_FOLLOW_UP = "follow_up"  # 跟进对话
    INTENT_CORRECTION = "correction"  # 纠正错误
    INTENT_GREETING = "greeting"  # 问候
    INTENT_GOODBYE = "goodbye"  # 告别
    INTENT_UNKNOWN = "unknown"  # 未知意图
    
    def __init__(self, config: Config):
        """
        初始化意图识别器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.llm = LLM(config)
        
        # 意图关键词映射（用于快速规则匹配）
        self.intent_keywords = {
            self.INTENT_GREETING: ["你好", "hello", "hi", "早上好", "下午好", "晚上好", "您好"],
            self.INTENT_GOODBYE: ["再见", "bye", "goodbye", "拜拜", "谢谢", "感谢"],
            self.INTENT_QUERY: ["什么", "如何", "为什么", "哪里", "什么时候", "谁", "多少", "查询", "搜索", "找"],
            self.INTENT_TASK: ["执行", "运行", "计算", "生成", "创建", "处理", "做", "完成"],
            self.INTENT_CLARIFICATION: ["什么意思", "不明白", "不清楚", "解释", "说明", "详细"],
            self.INTENT_CORRECTION: ["不对", "错了", "不是", "纠正", "修改", "更正"],
        }
    
    def recognize(
        self, 
        user_message: str, 
        state: AgentState,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        识别用户意图
        
        Args:
            user_message: 用户消息
            state: Agent当前状态
            conversation_history: 对话历史（可选）
            
        Returns:
            识别出的意图类型
        """
        # 1. 先使用规则匹配快速识别常见意图
        rule_intent = self._rule_based_recognition(user_message)
        if rule_intent and rule_intent != self.INTENT_UNKNOWN:
            return rule_intent
        
        # 2. 使用LLM进行更精确的意图识别
        llm_intent = self._llm_based_recognition(
            user_message,
            state,
            conversation_history
        )
        
        return llm_intent or self.INTENT_QUERY  # 默认返回查询意图
    
    def recognize_with_confidence(
        self,
        user_message: str,
        state: AgentState,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        识别用户意图并返回置信度
        
        Args:
            user_message: 用户消息
            state: Agent当前状态
            conversation_history: 对话历史（可选）
            
        Returns:
            意图识别结果，包含intent_type, confidence, reasoning等
        """
        # 规则匹配
        rule_intent = self._rule_based_recognition(user_message)
        
        # LLM识别
        llm_result = self._llm_based_recognition_with_confidence(
            user_message,
            state,
            conversation_history
        )
        
        # 如果规则匹配和LLM识别一致，提高置信度
        if rule_intent == llm_result.get("intent_type"):
            confidence = min(1.0, llm_result.get("confidence", 0.5) + 0.2)
        else:
            confidence = llm_result.get("confidence", 0.5)
        
        return {
            "intent_type": llm_result.get("intent_type", rule_intent),
            "confidence": confidence,
            "reasoning": llm_result.get("reasoning", ""),
            "rule_match": rule_intent
        }
    
    def _rule_based_recognition(self, user_message: str) -> str:
        """
        基于规则的意图识别（快速匹配）
        
        Args:
            user_message: 用户消息
            
        Returns:
            识别出的意图类型
        """
        user_message_lower = user_message.lower()
        
        # 检查每个意图的关键词
        for intent_type, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in user_message_lower:
                    return intent_type
        
        return self.INTENT_UNKNOWN
    
    def _llm_based_recognition(
        self,
        user_message: str,
        state: AgentState,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        基于LLM的意图识别
        
        Args:
            user_message: 用户消息
            state: Agent当前状态
            conversation_history: 对话历史
            
        Returns:
            识别出的意图类型
        """
        # 构建prompt
        system_prompt = """你是一个意图识别专家。请分析用户消息，识别用户的意图类型。

意图类型说明：
- query: 查询信息（如"什么是合同法"、"如何申请专利"）
- task: 执行任务（如"计算123+456"、"搜索相关信息"）
- clarification: 澄清问题（如"什么意思"、"能详细说明吗"）
- follow_up: 跟进对话（如"然后呢"、"还有吗"）
- correction: 纠正错误（如"不对"、"错了"）
- greeting: 问候（如"你好"、"早上好"）
- goodbye: 告别（如"再见"、"谢谢"）

请只返回意图类型，不要返回其他内容。"""
        
        # 构建上下文
        context_parts = [f"用户消息: {user_message}"]
        
        if state != AgentState.IDLE:
            context_parts.append(f"当前Agent状态: {state.value}")
        
        if conversation_history:
            recent_history = conversation_history[-3:]  # 只取最近3条
            context_parts.append("\n最近对话历史:")
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    context_parts.append(f"{role}: {content[:100]}")
        
        user_prompt = "\n".join(context_parts) + "\n\n请识别用户意图类型："
        
        try:
            # 使用LLM识别意图
            response = self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.1,  # 使用低温度以获得更稳定的结果
                max_tokens=50
            )
            
            # 提取意图类型
            intent = response.strip().lower()
            
            # 验证意图类型是否有效
            valid_intents = [
                self.INTENT_QUERY, self.INTENT_TASK, self.INTENT_CLARIFICATION,
                self.INTENT_FOLLOW_UP, self.INTENT_CORRECTION,
                self.INTENT_GREETING, self.INTENT_GOODBYE
            ]
            
            for valid_intent in valid_intents:
                if valid_intent in intent:
                    return valid_intent
            
            return self.INTENT_QUERY  # 默认返回查询意图
        
        except Exception as e:
            print(f"Warning: LLM intent recognition failed: {e}")
            return self.INTENT_QUERY  # 失败时返回默认意图
    
    def _llm_based_recognition_with_confidence(
        self,
        user_message: str,
        state: AgentState,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        基于LLM的意图识别（带置信度）
        
        Args:
            user_message: 用户消息
            state: Agent当前状态
            conversation_history: 对话历史
            
        Returns:
            意图识别结果，包含intent_type, confidence, reasoning
        """
        # 构建prompt
        system_prompt = """你是一个意图识别专家。请分析用户消息，识别用户的意图类型，并给出置信度。

意图类型说明：
- query: 查询信息
- task: 执行任务
- clarification: 澄清问题
- follow_up: 跟进对话
- correction: 纠正错误
- greeting: 问候
- goodbye: 告别

请以JSON格式返回结果：
{
    "intent_type": "意图类型",
    "confidence": 0.0-1.0之间的置信度,
    "reasoning": "识别理由"
}"""
        
        # 构建上下文
        context_parts = [f"用户消息: {user_message}"]
        
        if state != AgentState.IDLE:
            context_parts.append(f"当前Agent状态: {state.value}")
        
        if conversation_history:
            recent_history = conversation_history[-3:]
            context_parts.append("\n最近对话历史:")
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    context_parts.append(f"{role}: {content[:100]}")
        
        user_prompt = "\n".join(context_parts) + "\n\n请识别用户意图："
        
        try:
            # 使用LLM识别意图
            response = self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            # 尝试解析JSON
            import json
            try:
                result = json.loads(response)
                return {
                    "intent_type": result.get("intent_type", self.INTENT_QUERY),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", "")
                }
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试提取意图类型
                intent = self._extract_intent_from_text(response)
                return {
                    "intent_type": intent,
                    "confidence": 0.5,
                    "reasoning": response
                }
        
        except Exception as e:
            print(f"Warning: LLM intent recognition failed: {e}")
            return {
                "intent_type": self.INTENT_QUERY,
                "confidence": 0.3,
                "reasoning": f"Recognition failed: {str(e)}"
            }
    
    def _extract_intent_from_text(self, text: str) -> str:
        """从文本中提取意图类型"""
        text_lower = text.lower()
        valid_intents = [
            self.INTENT_QUERY, self.INTENT_TASK, self.INTENT_CLARIFICATION,
            self.INTENT_FOLLOW_UP, self.INTENT_CORRECTION,
            self.INTENT_GREETING, self.INTENT_GOODBYE
        ]
        
        for intent in valid_intents:
            if intent in text_lower:
                return intent
        
        return self.INTENT_QUERY
