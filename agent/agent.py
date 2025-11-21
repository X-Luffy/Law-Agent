"""最终的Agent类"""
from typing import Optional, Dict, Any
from .toolcall import ToolCallAgent
from ..schema import AgentState, Memory
from ..config.config import Config
from ..tools.tool_manager import ToolManager
from ..memory.memory_manager import MemoryManager
from ..context.manager import ContextManager
from ..intent.recognizer import IntentRecognizer
from ..intent.state_tracker import StateTracker
from ..reflection.self_reflection import SelfReflection
from ..llm.llm import LLM
from ..rag.rag_manager import RAGManager


class Agent(ToolCallAgent):
    """最终的Agent类，整合所有功能模块"""
    
    def __init__(
        self,
        name: str = "agent",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 30
    ):
        """
        初始化Agent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
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
        self.intent_recognizer = IntentRecognizer(config)
        self.state_tracker = StateTracker(config)
        self.self_reflection = SelfReflection(config)
        self.llm = LLM(config)
        self.rag_manager = RAGManager(config)
        
        # 初始化工具管理器
        tool_manager = ToolManager(config)
        
        # 调用父类初始化
        super().__init__(
            name=name,
            description=description or "A comprehensive agent with full capabilities",
            system_prompt=system_prompt,
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
        # 1. 识别用户意图
        conversation_history = [msg.to_dict() for msg in self.memory.messages]
        intent = self.intent_recognizer.recognize(
            user_message,
            self.state,
            conversation_history
        )
        
        # 2. 更新状态追踪
        self.state_tracker.update_state(self, user_message, intent)
        
        # 3. 检索相关记忆
        # 使用memory的messages作为session标识
        session_id = f"session_{len(self.memory.messages)}"
        relevant_memory = self.memory_manager.retrieve_relevant_memory(
            user_message,
            session_id
        )
        
        # 3.5. 根据意图决定是否使用RAG检索
        rag_result = None
        if intent in ["query", "task"]:
            # 判断是否需要RAG检索（法律问题或需要实时信息）
            needs_rag = self._should_use_rag(user_message, intent)
            if needs_rag:
                try:
                    # 优先使用法律库RAG（如果有法律关键词）
                    if self._is_legal_query(user_message):
                        rag_result = self.rag_manager.retrieve_and_generate(
                            query=user_message,
                            rag_type="legal",
                            top_k=5
                        )
                    else:
                        # 使用Web RAG（需要实时信息）
                        rag_result = self.rag_manager.retrieve_and_generate(
                            query=user_message,
                            rag_type="web",
                            top_k=5
                        )
                except Exception as e:
                    print(f"Warning: RAG retrieval failed: {e}")
        
        # 4. 管理上下文
        conversation_history = [msg.to_dict() for msg in self.memory.messages]
        
        # 如果有RAG结果，添加到relevant_memory中
        if rag_result and rag_result.get("answer"):
            # relevant_memory是字典，包含long_term和short_term
            if isinstance(relevant_memory, dict):
                # 将RAG结果添加到long_term记忆中
                if "long_term" not in relevant_memory:
                    relevant_memory["long_term"] = []
                relevant_memory["long_term"].append({
                    "content": rag_result["answer"],
                    "metadata": {
                        "type": "rag_result",
                        "source": rag_result.get("answer_source", "unknown")
                    },
                    "score": 1.0  # RAG结果的相关度设为1.0
                })
            else:
                # 如果relevant_memory不是字典，转换为字典格式
                relevant_memory = {
                    "long_term": [relevant_memory] if relevant_memory else [],
                    "short_term": []
                }
                relevant_memory["long_term"].append({
                    "content": rag_result["answer"],
                    "metadata": {
                        "type": "rag_result",
                        "source": rag_result.get("answer_source", "unknown")
                    },
                    "score": 1.0
                })
        
        context = self.context_manager.get_context(
            conversation_history,
            relevant_memory
        )
        
        # 如果有RAG结果，添加到context中
        if rag_result:
            context["rag_result"] = rag_result
        
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
                intent=intent,
                tool_results=tool_results
            )
        except TimeoutError as e:
            # 超时错误，尝试重试一次
            try:
                response = self._generate_response(
                    user_message=user_message,
                    context=context,
                    intent=intent,
                    tool_results=tool_results
                )
            except Exception as retry_error:
                response = f"抱歉，生成回复时遇到错误: {str(retry_error)}。请稍后重试。"
        except Exception as e:
            response = f"抱歉，生成回复时遇到错误: {str(e)}。请稍后重试。"
        
        # 7.5. 判断是否为专业回答（基于文档/法律条文）
        is_professional = self._is_professional_answer(response, context, tool_results)
        if is_professional:
            self.state = AgentState.PROFESSIONAL_ANSWER
        
        # 8. Self-reflection（可选）
        if self.config.reflection_enabled:
            reflection_result = self.self_reflection.reflect(
                user_message,
                response,
                {},
                self
            )
            if reflection_result.get("should_improve"):
                # TODO: 根据反思结果改进回复
                pass
        
        # 9. 保存对话到记忆
        self.memory_manager.save_conversation(
            session_id,
            user_message,
            response,
            intent
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
        
        # 从RAG结果中提取来源
        if rag_result and rag_result.get("sources"):
            for source in rag_result["sources"]:
                if isinstance(source, dict):
                    url = source.get("url", "")
                    title = source.get("title", "")
                    if url:
                        sources_info.append({
                            "url": url,
                            "title": title or url[:50] + "..." if len(url) > 50 else url,
                            "snippet": source.get("snippet", "")[:100]
                        })
        
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
        intent: str,
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
        system_prompt = self.system_prompt or """你是一个专业的AI助手，特别擅长法律相关问题的回答。请根据用户的问题和上下文信息，提供准确、完整、有帮助的回答。

**重要约束**：
1. **基于文档回答**：如果提供了相关文档、法律条文或检索到的信息，必须严格基于这些信息回答，不得编造或推测
2. **无法回答时明确说明**：如果无法从提供的文档或信息中找到答案，必须明确说明"根据提供的文档，无法找到相关信息"或"无法回答此问题"
3. **引用来源**：如果使用了文档、法律条文或网络搜索结果，必须明确引用来源
4. **区分专业回答和一般回答**：
   - 专业回答（法律条文、案例等）：必须基于检索到的文档，明确标注来源
   - 一般回答：可以基于常识和知识，但要说明这是基于一般知识
5. **禁止幻觉**：严禁编造法律条文、案例或事实，如果不知道，必须说明

**回答格式**：
- 如果基于文档：开头说明"根据检索到的文档/法律条文..."
- 如果无法回答：明确说明"无法回答"或"未找到相关信息"
- 如果是一般回答：说明"基于一般知识..."

要求：
1. 回答要准确、完整、专业
2. 如果使用了工具，请整合工具结果并说明来源
3. 如果上下文中有相关信息，请引用
4. 使用清晰、易懂的语言
5. 如果无法回答，请明确说明"""
        
        # 构建用户消息
        user_prompt_parts = [f"用户问题：{user_message}"]
        
        # 添加意图信息
        if intent:
            user_prompt_parts.append(f"用户意图：{intent}")
        
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
        
        # 添加RAG结果（如果有）
        if context.get("rag_result"):
            rag_result = context["rag_result"]
            if rag_result.get("answer"):
                user_prompt_parts.append(f"\n检索到的信息：{rag_result['answer']}")
                if rag_result.get("sources"):
                    user_prompt_parts.append(f"\n信息来源：")
                    for source in rag_result["sources"][:3]:
                        if isinstance(source, dict):
                            source_text = source.get("url", "") or source.get("title", "") or str(source)
                            user_prompt_parts.append(f"- {source_text}")
        
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
    
    def _is_professional_answer(
        self,
        response: str,
        context: Dict[str, Any],
        tool_results: str
    ) -> bool:
        """
        判断是否为专业回答（基于文档/法律条文）
        
        Args:
            response: Agent回复
            context: 上下文信息
            tool_results: 工具执行结果
            
        Returns:
            是否为专业回答
        """
        # 检查回复中是否包含文档引用
        professional_keywords = [
            "根据文档", "根据法律条文", "根据检索", "根据案例",
            "法律条文", "法律规定", "法条", "案例", "判决",
            "来源：", "参考：", "依据："
        ]
        
        response_lower = response.lower()
        if any(keyword in response_lower for keyword in professional_keywords):
            return True
        
        # 检查是否使用了RAG检索
        if context.get("long_term_memory") or context.get("refined_context"):
            return True
        
        # 检查工具结果中是否包含文档内容
        if tool_results and ("document" in tool_results.lower() or "法律" in tool_results):
            return True
        
        return False
    
    def _should_use_rag(self, user_message: str, intent: str) -> bool:
        """
        判断是否应该使用RAG检索
        
        Args:
            user_message: 用户消息
            intent: 用户意图
            
        Returns:
            是否应该使用RAG
        """
        # 如果是查询意图，检查是否需要实时信息或法律信息
        if intent == "query":
            # 检查是否包含实时信息关键词
            realtime_keywords = ["天气", "今天", "现在", "最新", "实时", "当前"]
            if any(keyword in user_message for keyword in realtime_keywords):
                return True
            
            # 检查是否包含法律关键词
            if self._is_legal_query(user_message):
                return True
        
        # 如果是任务意图，可能需要搜索信息
        if intent == "task":
            task_keywords = ["搜索", "查找", "查询", "获取", "检索"]
            if any(keyword in user_message for keyword in task_keywords):
                return True
        
        return False
    
    def _is_legal_query(self, user_message: str) -> bool:
        """
        判断是否为法律相关查询
        
        Args:
            user_message: 用户消息
            
        Returns:
            是否为法律查询
        """
        legal_keywords = [
            "法律", "法条", "法规", "条例", "规定", "条款", "合同",
            "诉讼", "判决", "案例", "律师", "法院", "司法", "立法"
        ]
        return any(keyword in user_message for keyword in legal_keywords)

