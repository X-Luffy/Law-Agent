"""Self-reflection模块"""
from typing import Dict, Any, List
from ..config.config import Config
from ..llm.llm import LLM


class SelfReflection:
    """Self-reflection模块，使用不同角色的LLM进行反思"""
    
    def __init__(self, config: Config):
        """
        初始化Self-reflection模块
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.roles = config.reflection_roles
        self.llm = LLM(config)
        self.role_prompts = self._initialize_role_prompts()
    
    def _initialize_role_prompts(self) -> Dict[str, str]:
        """
        初始化不同角色的prompt
        
        Returns:
            角色到prompt的字典
        """
        return {
            "critic": """You are a critical reviewer. Your task is to analyze the conversation and identify:
1. Issues or errors in the response
2. Areas where the response could be improved
3. Missing information or incomplete answers
4. Inconsistencies or contradictions

Be constructive and specific in your critique.""",
            
            "improver": """You are an improvement advisor. Based on the critique provided, your task is to:
1. Suggest specific improvements to the response
2. Provide concrete examples of how to improve
3. Recommend alternative approaches or solutions
4. Identify what information or context might be needed

Focus on actionable improvements.""",
            
            "validator": """You are a validator. Your task is to check:
1. Is the response accurate and factually correct?
2. Is the response complete and addresses all parts of the question?
3. Is the response appropriate for the context and user's intent?
4. Are there any logical errors or inconsistencies?

Provide a clear validation result with specific findings."""
        }
    
    def reflect(
        self,
        user_message: str,
        response: str,
        tool_results: Dict[str, Any],
        agent
    ) -> Dict[str, Any]:
        """
        进行Self-reflection
        
        Args:
            user_message: 用户消息
            response: Agent回复
            tool_results: 工具执行结果
            agent: Agent实例
            
        Returns:
            反思结果，包含critique, improvements, validation, should_improve等
        """
        # 构建对话上下文
        context = self._build_context(user_message, response, tool_results, agent)
        
        reflection_results = {}
        
        # 让不同角色的LLM进行反思
        for role in self.roles:
            try:
                role_result = self._reflect_with_role(
                    role,
                    user_message,
                    response,
                    tool_results,
                    context
                )
                reflection_results[role] = role_result
            except Exception as e:
                print(f"Warning: Failed to reflect with role '{role}': {e}")
                reflection_results[role] = {
                    "result": f"Error: {str(e)}",
                    "success": False
                }
        
        # 综合反思结果
        final_result = self._synthesize_reflection(reflection_results)
        
        return final_result
    
    def _build_context(
        self,
        user_message: str,
        response: str,
        tool_results: Dict[str, Any],
        agent
    ) -> str:
        """
        构建反思上下文
        
        Args:
            user_message: 用户消息
            response: Agent回复
            tool_results: 工具执行结果
            agent: Agent实例
            
        Returns:
            上下文文本
        """
        context_parts = []
        
        # 添加用户消息
        context_parts.append(f"User Message: {user_message}")
        
        # 添加Agent回复
        context_parts.append(f"Agent Response: {response}")
        
        # 添加工具执行结果
        if tool_results:
            context_parts.append("\nTool Results:")
            for tool_name, result in tool_results.items():
                context_parts.append(f"- {tool_name}: {str(result)[:200]}")
        
        # 添加最近的对话历史（如果有）
        if hasattr(agent, 'memory') and agent.memory:
            recent_messages = agent.memory.get_recent_messages(5)
            if recent_messages:
                context_parts.append("\nRecent Conversation History:")
                for msg in recent_messages[-3:]:  # 只取最近3条
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        context_parts.append(f"{msg.role}: {msg.content[:100]}")
        
        return "\n".join(context_parts)
    
    def _reflect_with_role(
        self,
        role: str,
        user_message: str,
        response: str,
        tool_results: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        使用特定角色进行反思
        
        Args:
            role: 角色名称
            user_message: 用户消息
            response: Agent回复
            tool_results: 工具执行结果
            context: 上下文信息
            
        Returns:
            该角色的反思结果
        """
        # 获取该角色的prompt
        role_prompt = self.role_prompts.get(role, "")
        
        if not role_prompt:
            return {
                "result": f"Unknown role: {role}",
                "success": False
            }
        
        # 构建反思prompt
        reflection_prompt = f"""{role_prompt}

Context:
{context}

Please provide your analysis:"""
        
        try:
            # 调用LLM进行反思
            reflection_result = self.llm.chat(
                messages=[{"role": "user", "content": reflection_prompt}],
                temperature=0.3,  # 使用较低温度以获得更稳定的反思
                max_tokens=1000
            )
            
            return {
                "result": reflection_result,
                "success": True,
                "role": role
            }
        
        except Exception as e:
            return {
                "result": f"Error during reflection: {str(e)}",
                "success": False,
                "role": role
            }
    
    def _synthesize_reflection(
        self,
        reflection_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        综合不同角色的反思结果
        
        Args:
            reflection_results: 各角色的反思结果
            
        Returns:
            综合后的反思结果
        """
        # 提取各角色的反思结果
        critiques = []
        improvements = []
        validations = []
        
        for role, result in reflection_results.items():
            if not result.get("success", False):
                continue
            
            reflection_text = result.get("result", "")
            
            if role == "critic":
                critiques.append(reflection_text)
            elif role == "improver":
                improvements.append(reflection_text)
            elif role == "validator":
                validations.append(reflection_text)
        
        # 判断是否需要改进回复
        should_improve = False
        improvement_reasons = []
        
        # 检查critic的反馈
        if critiques:
            # 简单的关键词检测（可以后续使用LLM进行更智能的判断）
            critical_keywords = ["error", "issue", "problem", "missing", "incomplete", "incorrect", "wrong"]
            for critique in critiques:
                critique_lower = critique.lower()
                if any(keyword in critique_lower for keyword in critical_keywords):
                    should_improve = True
                    improvement_reasons.append("Critic identified issues")
                    break
        
        # 检查validator的反馈
        if validations:
            validation_keywords = ["incorrect", "incomplete", "inappropriate", "error", "wrong"]
            for validation in validations:
                validation_lower = validation.lower()
                if any(keyword in validation_lower for keyword in validation_keywords):
                    should_improve = True
                    improvement_reasons.append("Validator found problems")
                    break
        
        # 综合改进建议
        all_improvements = "\n\n".join(improvements) if improvements else "No specific improvements suggested."
        
        return {
            "should_improve": should_improve,
            "improvement_reasons": improvement_reasons,
            "critique": "\n\n".join(critiques) if critiques else "No critique provided.",
            "improvements": all_improvements,
            "validation": "\n\n".join(validations) if validations else "No validation provided.",
            "reflection_results": reflection_results,
            "summary": self._generate_reflection_summary(
                should_improve,
                improvement_reasons,
                critiques,
                improvements,
                validations
            )
        }
    
    def _generate_reflection_summary(
        self,
        should_improve: bool,
        improvement_reasons: List[str],
        critiques: List[str],
        improvements: List[str],
        validations: List[str]
    ) -> str:
        """
        生成反思摘要
        
        Args:
            should_improve: 是否需要改进
            improvement_reasons: 改进原因列表
            critiques: 批评列表
            improvements: 改进建议列表
            validations: 验证结果列表
            
        Returns:
            反思摘要文本
        """
        summary_parts = []
        
        if should_improve:
            summary_parts.append("Reflection Summary: Improvements needed.")
            if improvement_reasons:
                summary_parts.append(f"Reasons: {', '.join(improvement_reasons)}")
        else:
            summary_parts.append("Reflection Summary: Response is acceptable.")
        
        if critiques:
            summary_parts.append(f"\nCritiques: {len(critiques)} critique(s) provided.")
        
        if improvements:
            summary_parts.append(f"\nImprovements: {len(improvements)} improvement suggestion(s).")
        
        if validations:
            summary_parts.append(f"\nValidations: {len(validations)} validation(s) completed.")
        
        return "\n".join(summary_parts)
