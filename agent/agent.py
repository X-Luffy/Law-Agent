"""最终的Agent类"""
from typing import Optional, Dict, Any
from .toolcall import ToolCallAgent
# 处理相对导入问题
try:
    from ..schema import AgentState, Memory
    from ..config.config import Config
    from ..tools.tool_manager import ToolManager
    from ..memory.memory_manager import MemoryManager
    from ..memory.manager import ContextManager
    from ..models.llm import LLM
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from schema import AgentState, Memory
    from config.config import Config
    from tools.tool_manager import ToolManager
    from memory.memory_manager import MemoryManager
    from memory.manager import ContextManager
    from models.llm import LLM


class Agent(ToolCallAgent):
    """最终的Agent类，整合所有功能模块"""
    
    def __init__(
        self,
        name: str = "agent",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10
    ):
        """
        初始化Agent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数
        """
        # 初始化各个模块
        if config is None:
            config = Config()
        
        self.memory_manager = MemoryManager(config)
        self.context_manager = ContextManager(config)
        self.llm = LLM(config)
        
        # 初始化工具管理器
        tool_manager = ToolManager(config)
        
        # 调用父类初始化
        super().__init__(
            name=name,
            description=description or "A comprehensive agent with full capabilities",
            system_prompt=system_prompt,
            next_step_prompt=next_step_prompt,
            config=config,
            memory=memory,
            state=state,
            max_steps=max_steps,
            tool_manager=tool_manager
        )
    
    async def process_message(self, user_message: str) -> str:
        """
        处理用户消息（高级接口）
        
        Args:
            user_message: 用户消息
            
        Returns:
            Agent回复
        """
        # 1. 使用Agent的memory和state进行状态维护
        # memory已经通过继承的BaseAgent管理，state通过AgentState管理
        
        # 3. 检索相关记忆
        # 使用memory的messages作为session标识
        session_id = f"session_{len(self.memory.messages)}"
        relevant_memory = self.memory_manager.retrieve_relevant_memory(
            user_message,
            session_id
        )
        
        # 4. 管理上下文
        conversation_history = [msg.to_dict() for msg in self.memory.messages]
        
        context = self.context_manager.get_context(
            conversation_history,
            relevant_memory
        )
        
        # 5. 运行Agent（思考-行动循环）
        # 确保状态为IDLE（run方法需要）
        if self.state != AgentState.IDLE:
            self.state = AgentState.IDLE
        # 重置步数计数器
        self.current_step = 0
        # run方法会添加用户消息到记忆
        result = await self.run(user_message)
        
        # 7. 生成最终回复（使用LLM生成，带重试机制）
        tool_results = result  # 保存工具执行结果，供后续使用
        try:
            response = self._generate_response(
                user_message=user_message,
                context=context,
                tool_results=tool_results
            )
        except TimeoutError as e:
            # 超时错误，尝试重试一次
            try:
                response = self._generate_response(
                    user_message=user_message,
                    context=context,
                    tool_results=tool_results
                )
            except Exception as retry_error:
                response = f"抱歉，生成回复时遇到错误: {str(retry_error)}。请稍后重试。"
        except Exception as e:
            response = f"抱歉，生成回复时遇到错误: {str(e)}。请稍后重试。"
        
        # 7.5. 判断是否为专业回答（基于文档/法律条文）
        # TODO: 实现更专业的判断逻辑
        # is_professional = self._is_professional_answer(response, context, tool_results)
        # if is_professional:
        #     self.state = AgentState.PROFESSIONAL_ANSWER
        
        # 8. Agent的think过程已经包含了反思机制（通过react循环）
        
        # 9. 保存对话到记忆
        self.memory_manager.save_conversation(
            session_id,
            user_message,
            response,
            "query"  # 默认意图类型
        )
        
        # 9. 保存精炼后的上下文到长期记忆（如果有）
        if context.get("refined_context"):
            refined_ctx = context["refined_context"]
            if isinstance(refined_ctx, dict) and refined_ctx.get("summary"):
                self.memory_manager.save_refined_context(
                    summary=refined_ctx.get("summary", ""),
                    key_points=refined_ctx.get("key_points", []),
                    important_info=refined_ctx.get("important_info", {})
                )
        
        # 10. 添加来源信息到回复中（供前端显示）
        sources_info = []
        
        # 从工具执行结果中提取URL（如果工具返回了URL）
        if tool_results and isinstance(tool_results, str):
            # 尝试从工具结果中提取URL
            import re
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, tool_results)
            for url in urls:
                # 检查是否已经在sources_info中
                if not any(s.get("url") == url for s in sources_info):
                    sources_info.append({
                        "url": url,
                        "title": url[:50] + "..." if len(url) > 50 else url,
                        "snippet": ""
                    })
        
        # 如果有来源信息，添加到回复末尾（使用markdown格式，前端可以提取）
        if sources_info:
            sources_text = "\n\n---\n**🔗 信息来源（点击查看原文）：**\n"
            for i, source in enumerate(sources_info[:5], 1):  # 最多显示5个来源
                url = source.get("url", "")
                title = source.get("title", url)
                snippet = source.get("snippet", "")
                
                if url:
                    if snippet:
                        sources_text += f"{i}. [{title}]({url})\n   *{snippet}...*\n\n"
                    else:
                        sources_text += f"{i}. [{title}]({url})\n\n"
            
            response = response + sources_text
        
        # 11. 添加回复到记忆
        self.update_memory("assistant", response)
        
        return response
    
    def _generate_response(
        self,
        user_message: str,
        context: Dict[str, Any],
        tool_results: str
    ) -> str:
        """
        生成最终回复
        
        Args:
            user_message: 用户消息
            context: 上下文信息
            intent: 用户意图
            tool_results: 工具执行结果
            
        Returns:
            Agent回复
        """
        # 构建系统提示词（增强版，避免幻觉）
        try:
            from ..prompt.agent_prompts import AGENT_SYSTEM_PROMPT
        except (ImportError, ValueError):
            # 如果相对导入失败，使用绝对导入
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.agent_prompts import AGENT_SYSTEM_PROMPT
        system_prompt = self.system_prompt or AGENT_SYSTEM_PROMPT
        
        # 构建用户消息
        user_prompt_parts = [f"用户问题：{user_message}"]
        
        # 意图信息已通过Agent的think过程处理
        
        # 添加上下文信息
        if context.get("recent_messages"):
            user_prompt_parts.append("\n最近对话历史：")
            for msg in context["recent_messages"][-5:]:  # 只取最近5条
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    user_prompt_parts.append(f"{role}: {content[:200]}")
        
        # 添加精炼后的上下文
        if context.get("refined_context"):
            refined_ctx = context["refined_context"]
            if isinstance(refined_ctx, dict) and refined_ctx.get("summary"):
                user_prompt_parts.append("\n往期对话摘要：")
                user_prompt_parts.append(refined_ctx.get("summary", "")[:500])
        
        # 添加长期记忆
        if context.get("long_term_memory"):
            long_term = context["long_term_memory"]
            if long_term:
                user_prompt_parts.append("\n相关历史记忆：")
                for memory in long_term[:3]:  # 只取前3条
                    content = memory.get("content", "")
                    if content:
                        user_prompt_parts.append(f"- {content[:200]}")
        
        # 添加工具执行结果
        if tool_results and tool_results != "No steps executed":
            user_prompt_parts.append(f"\n工具执行结果：{tool_results}")
        
        # 添加答案来源要求
        user_prompt_parts.append("\n**请根据以上信息回答，并明确说明：**")
        user_prompt_parts.append("1. 答案来源（基于文档/网络搜索/知识库/一般知识/无法回答）")
        user_prompt_parts.append("2. 如果基于文档，请引用具体来源")
        user_prompt_parts.append("3. 如果无法回答，请明确说明")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        # 构建消息列表
        messages = []
        
        # 添加历史对话（从memory中获取）
        for msg in self.memory.messages[-10:]:  # 只取最近10条
            messages.append(msg.to_dict())
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            # 使用LLM生成回复
            response = self.llm.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens
            )
            return response
        except Exception as e:
            return f"生成回复时出错: {str(e)}"
    
    # TODO: 实现更专业的判断逻辑
    # def _is_professional_answer(
    #     self,
    #     response: str,
    #     context: Dict[str, Any],
    #     tool_results: str
    # ) -> bool:
    #     """
    #     判断是否为专业回答（基于文档/法律条文）
    #     
    #     Args:
    #         response: Agent回复
    #         context: 上下文信息
    #         tool_results: 工具执行结果
    #         
    #     Returns:
    #         是否为专业回答
    #     """
    #     pass
    
    # TODO: 实现更智能的工具使用判断逻辑（如果需要）
    # def _should_use_tool(self, user_message: str, intent: str) -> bool:
    #     """
    #     判断是否应该使用特定工具
    #     
    #     Args:
    #         user_message: 用户消息
    #         intent: 用户意图
    #         
    #     Returns:
    #         是否应该使用工具
    #     """
    #     pass
    
    # TODO: 实现更准确的法律查询判断逻辑
    # def _is_legal_query(self, user_message: str) -> bool:
    #     """
    #     判断是否为法律相关查询
    #     
    #     Args:
    #         user_message: 用户消息
    #         
    #     Returns:
    #         是否为法律查询
    #     """
    #     pass
    
    async def think(self) -> bool:
        """
        思考阶段：处理当前状态并决定下一步行动（参考manus.py）
        
        Returns:
            是否需要执行行动
        """
        # TODO: MCP连接逻辑（如果需要）
        # if not self._initialized:
        #     await self.initialize_mcp_servers()
        #     self._initialized = True
        
        # TODO: 可以在这里添加browser context helper逻辑（如果需要）
        # original_prompt = self.next_step_prompt
        # recent_messages = self.memory.messages[-3:] if self.memory.messages else []
        # browser_in_use = any(...)
        # if browser_in_use:
        #     self.next_step_prompt = await self.browser_context_helper.format_next_step_prompt()
        
        # 调用父类的think方法
        result = await super().think()
        
        # TODO: 恢复原始prompt（如果需要）
        # self.next_step_prompt = original_prompt
        
        return result
    
    async def initialize_mcp_servers(self) -> None:
        """
        初始化MCP服务器连接（如果需要）
        
        TODO: 实现MCP服务器连接逻辑
        MCP (Model Context Protocol) 可以通过SSE或stdio连接到MCP服务器，
        并使用服务器提供的工具。如果MCP服务器提供web_browser相关工具，
        可以通过connect_mcp_server方法连接并添加这些工具。
        """
        pass

