"""ToolCallAgent类"""
import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from .react import ReActAgent
# 处理相对导入问题
try:
    from ..tools.tool_manager import ToolManager
    from ..tools.base import BaseTool
    from ..schema import AgentState, Memory, Message
    from ..config.config import Config
    from ..models.llm import LLM
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from tools.tool_manager import ToolManager
    from tools.base import BaseTool
    from schema import AgentState, Memory, Message
    from config.config import Config
    from models.llm import LLM


class ToolCallAgent(ReActAgent):
    """ToolCallAgent，继承ReActAgent，添加可用工具集合，实现think和act方法"""
    
    def __init__(
        self,
        name: str = "toolcall_agent",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10,
        available_tools: Optional[List[BaseTool]] = None,
        tool_manager: Optional[ToolManager] = None,
        max_observe: Optional[Union[int, bool]] = None
    ):
        """
        初始化ToolCallAgent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词（会在think()中使用）
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数
            available_tools: 可用工具列表
            tool_manager: 工具管理器
            max_observe: 限制观察结果的最大长度（字符数），None表示不限制
        """
        super().__init__(
            name=name,
            description=description or "An agent that can execute tool calls",
            system_prompt=system_prompt,
            next_step_prompt=next_step_prompt,
            config=config,
            memory=memory,
            state=state,
            max_steps=max_steps
        )
        
        # 初始化工具管理器
        self.tool_manager = tool_manager or ToolManager(self.config)
        
        # 注册可用工具
        if available_tools:
            for tool in available_tools:
                self.tool_manager.register_tool(tool)
        
        # 结果限制配置
        self.max_observe = max_observe
        
        # 初始化LLM（用于Native Function Calling）
        self.llm = LLM(self.config)
        
        # 获取工具映射字典（工具名称 -> 执行函数）
        self.available_functions = self.tool_manager.get_available_functions()
        
        # 当前工具调用（从LLM响应中获取）
        self.current_tool_calls: List[Dict[str, Any]] = []
    
    async def think(self) -> bool:
        """
        思考阶段：使用Native Function Calling（LLM原生工具调用）
        
        Returns:
            是否需要执行行动
        """
        # 更新状态：思考阶段
        self.update_status(
            f"💭 Step {self.current_step}: 思考中...",
            "正在分析问题，决定下一步行动...",
            "running"
        )
        
        # 如果设置了next_step_prompt，添加到消息中
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.memory.add_message(user_msg)
        
        # 获取最近的对话上下文
        recent_messages = self.memory.get_recent_messages(10)  # 增加上下文长度，避免截断工具调用对
        
        # 转换消息为字典格式
        messages_dict = []
        for msg in recent_messages:
            if isinstance(msg, Message):
                messages_dict.append(msg.to_dict())
            elif isinstance(msg, dict):
                messages_dict.append(msg)
        
        # 修复DashScope/OpenAI API限制：tool消息必须跟在tool_calls消息之后
        # 如果第一条消息是tool类型，说明前面的assistant消息被截断了，需要丢弃这条tool消息
        while messages_dict and messages_dict[0].get("role") == "tool":
            print(f"Warning: Dropping orphaned tool message at start of context")
            messages_dict.pop(0)
        
        # 获取所有工具的JSON Schema
        tools_schema = self.tool_manager.get_tools_schema()
        
        # 构建系统提示词
        system_prompt = self.system_prompt or "You are a helpful assistant with access to various tools."
        
        # 调用LLM的chat_with_tools方法（Native Function Calling）
        try:
            response = self.llm.chat_with_tools(
                messages=messages_dict,
                tools=tools_schema,
                tool_choice="auto",  # 让模型自己决定是否使用工具
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=self.config.llm_max_tokens
            )
        except Exception as e:
            print(f"Error in LLM tool calling: {e}")
            self.update_memory("assistant", f"Error: {str(e)}")
            return False
        
        # 提取回复内容和工具调用
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        
        # 记录LLM的思考内容
        if content:
            print(f"✨ {self.name}'s thoughts: {content}")
        
        # 处理工具调用
        self.current_tool_calls = []
        if tool_calls:
            print(f"🛠️ {self.name} selected {len(tool_calls)} tools to use")
            tool_names = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_names.append(tool_name)
                print(f"🧰 Tool: {tool_name}, Arguments: {tool_call.get('function', {}).get('arguments', '')}")
                self.current_tool_calls.append(tool_call)
            
            # 更新状态：准备执行工具
            self.update_status(
                f"🛠️ Step {self.current_step}: 准备执行工具",
                f"准备调用工具: {', '.join(tool_names)}",
                "running"
            )
        else:
            # 没有工具调用，可能是生成最终回答
            if content and len(content) > 50:
                self.update_status(
                    f"📝 Step {self.current_step}: 生成最终回答",
                    "正在生成最终回答...",
                    "running"
                )
        
        # 创建assistant消息（包含内容和工具调用）
        if tool_calls:
            # 有工具调用
            assistant_msg = Message.from_tool_calls(
                content=content,
                tool_calls=self.current_tool_calls
            ) if hasattr(Message, 'from_tool_calls') else Message.assistant_message(
                content=content,
                tool_calls=self.current_tool_calls
            )
        else:
            # 没有工具调用，只有文本回复
            assistant_msg = Message.assistant_message(content=content)
        
        self.memory.add_message(assistant_msg)
        
        # 如果有工具调用，返回True表示需要执行行动
        if self.current_tool_calls:
            return True
        
        # 检查是否有工具执行结果
        has_tool_results = any(
            msg.role == "tool" for msg in self.memory.get_recent_messages(10)
        )
        
        # 如果已经有工具执行结果，需要检查是否已经生成了最终回答
        if has_tool_results:
            # 检查最后一条assistant消息是否在工具结果之后（说明已经生成了最终回答）
            recent_msgs = self.memory.get_recent_messages(20)
            last_tool_index = -1
            last_assistant_index = -1
            
            for i, msg in enumerate(recent_msgs):
                if msg.role == "tool":
                    last_tool_index = i
                elif msg.role == "assistant" and msg.content:
                    last_assistant_index = i
            
            # 如果最后一条assistant消息在工具结果之后，说明已经生成了最终回答
            if last_assistant_index > last_tool_index:
                # 检查这个回答是否足够完整（不是空的或只是思考内容）
                last_assistant_msg = recent_msgs[last_assistant_index]
                if last_assistant_msg.content and len(last_assistant_msg.content) > 50:
                    # 已经有完整的最终回答，可以结束
                    self.state = AgentState.FINISHED
                    return False
            
            # 如果有工具结果但还没有基于工具结果的最终回答
            # 当前LLM调用应该会生成最终回答（因为messages中包含了tool结果）
            # 如果content不为空，说明LLM已经生成了回答
            if content and len(content) > 50:
                # LLM已经基于工具结果生成了最终回答
                self.state = AgentState.FINISHED
                return False
            # 如果content为空或太短，可能是LLM还在思考，继续等待下一轮
        
        # 如果没有工具调用但有内容，检查是否可以结束
        if content and not has_tool_results:
            # 检查是否已经有完整的回答
            if len(content) > 50:  # 简单判断：内容较长可能是完整回答
                self.state = AgentState.FINISHED
                return False
        
        # 如果没有工具调用也没有内容，继续思考
        return False
    
    async def act(self) -> str:
        """
        行动阶段：执行工具调用
        
        Returns:
            工具执行结果
        """
        if not self.current_tool_calls:
            return "No tools to execute"
        
        results = []
        for idx, tool_call in enumerate(self.current_tool_calls):
            tool_name = tool_call.get("function", {}).get("name", "")
            # 更新状态：执行工具
            self.update_status(
                f"⚡ Step {self.current_step}: 执行工具 ({idx+1}/{len(self.current_tool_calls)})",
                f"正在执行工具: {tool_name}...",
                "running"
            )
            
            result = await self.execute_tool(tool_call)
            
            # 限制观察结果长度
            if self.max_observe and isinstance(self.max_observe, int):
                result = result[:self.max_observe]
            
            print(f"🎯 Tool '{tool_call['function']['name']}' completed: {result[:100] if len(result) > 100 else result}...")
            
            # 添加工具响应到记忆
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=tool_call.get("id", ""),
                name=tool_call["function"]["name"]
            )
            self.memory.add_message(tool_msg)
            results.append(result)
        
        # 清空工具调用
        self.current_tool_calls = []
        
        return "\n\n".join(results)
    
    async def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """
        执行单个工具调用（使用映射字典）
        
        Args:
            tool_call: 工具调用字典（来自LLM的tool_calls）
            
        Returns:
            工具执行结果
        """
        if not tool_call or not tool_call.get("function") or not tool_call["function"].get("name"):
            return "Error: Invalid command format"
        
        name = tool_call["function"]["name"]
        
        # 从映射字典中获取工具的执行函数
        tool_function = self.available_functions.get(name)
        
        if not tool_function:
            return f"Error: Unknown tool '{name}'"
        
        try:
            # 解析参数（LLM返回的arguments是JSON字符串）
            args_str = tool_call["function"].get("arguments", "{}")
            args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
            
            print(f"🔧 Activating tool: '{name}' with arguments: {args_dict}")
            
            # 构建上下文
            context = {
                "messages": [msg.to_dict() for msg in self.memory.get_recent_messages(10)],
                "max_results": args_dict.get("max_results", 5)
            }
            
            # 从参数中提取用户输入（兼容多种参数名）
            # 根据工具schema的不同，参数名可能不同
            # 对于document_tool，需要传递完整的args_dict作为context
            if name == "generate_legal_document":
                # 文档生成工具需要title, content, file_format参数
                context.update(args_dict)  # 将参数添加到context中
                tool_input = json.dumps(args_dict, ensure_ascii=False)  # 将参数转为JSON字符串
            else:
                tool_input = (
                    args_dict.get("query") or 
                    args_dict.get("url") or 
                    args_dict.get("city") or 
                    args_dict.get("code") or
                    args_dict.get("expression") or
                    args_dict.get("file_path") or
                    args_dict.get("input") or 
                    args_dict.get("user_input") or
                    str(args_dict)  # 如果都没有，将整个字典转为字符串
                )
            
            # 执行工具（使用映射字典中的函数）
            # 支持同步和异步工具
            if asyncio.iscoroutinefunction(tool_function):
                result = await tool_function(user_input=tool_input, context=context)
            else:
                result = tool_function(user_input=tool_input, context=context)
            
            # 格式化结果
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )
            
            # 限制观察结果长度
            if self.max_observe and isinstance(observation, str):
                if isinstance(self.max_observe, bool) and self.max_observe:
                    # 如果max_observe是True，使用默认限制
                    max_len = 2000
                else:
                    max_len = self.max_observe
                
                if len(observation) > max_len:
                    observation = observation[:max_len] + "\n\n[Output truncated...]"
            
            return observation
            
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            print(f"📝 Error: {error_msg}, arguments: {tool_call['function'].get('arguments')}")
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            print(f"🚨 {error_msg}")
            import traceback
            traceback.print_exc()
            return f"Error: {error_msg}"
    
    async def cleanup(self):
        """清理Agent使用的资源（参考标准实现）"""
        print(f"🧹 Cleaning up resources for agent '{self.name}'...")
        for tool_name, tool_instance in self.tool_manager.tools.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                tool_instance.cleanup
            ):
                try:
                    print(f"🧼 Cleaning up tool: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    print(f"🚨 Error cleaning up tool '{tool_name}': {e}")
        print(f"✨ Cleanup complete for agent '{self.name}'.")
    
    async def run(self, request: Optional[str] = None, status_callback=None, context: str = "") -> str:
        """
        运行Agent（不在这里清理，由execute_task完成后清理）
        
        Args:
            request: 可选的初始用户请求
            status_callback: 可选的状态回调函数
            context: 上下文信息（可选，用于无状态执行）
            
        Returns:
            执行结果摘要
        """
        # 不在run方法中清理，因为execute_task还需要进行Critic评估
        # 清理将在execute_task完成后进行
        return await super().run(request, status_callback, context)
    
    def _generate_tool_arguments(
        self,
        tool_name: str,
        user_query: str,
        recent_messages: List[Message]
    ) -> str:
        """
        使用LLM生成工具调用的参数
        
        Args:
            tool_name: 工具名称
            user_query: 用户查询
            recent_messages: 最近消息列表
            
        Returns:
            工具参数的JSON字符串
        """
        # 获取工具描述
        tool = self.tool_manager.get_tool(tool_name)
        if not tool:
            return "{}"
        
        tool_description = tool.get_description()
        
        # 构建prompt
        system_prompt = """你是一个工具参数生成助手。请根据用户查询和工具描述，生成工具调用所需的参数。
要求：
1. 参数必须是有效的JSON格式
2. 只包含工具需要的参数
3. 从用户查询中提取相关信息作为参数值"""
        
        user_prompt = f"""工具名称：{tool_name}
工具描述：{tool_description}
用户查询：{user_query}

请生成工具调用所需的参数（JSON格式）："""
        
        try:
            # 使用LLM生成参数
            response = self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.1,  # 使用低温度以获得更稳定的结果
                max_tokens=200
            )
            
            # 尝试解析JSON
            import json
            try:
                # 尝试提取JSON
                response = response.strip()
                if response.startswith("```"):
                    # 移除代码块标记
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                response = response.strip()
                
                # 解析JSON
                args = json.loads(response)
                return json.dumps(args, ensure_ascii=False)
            except json.JSONDecodeError:
                # 如果JSON解析失败，返回空字典
                return "{}"
        
        except Exception as e:
            print(f"Warning: Failed to generate tool arguments: {e}")
            return "{}"
    
    def _heuristic_tool_selection(
        self,
        user_query: str,
        messages_dict: List[Dict[str, Any]]
    ) -> List[str]:
        """
        基于关键词的启发式工具选择（当embedding选择失败时使用）
        
        Args:
            user_query: 用户查询
            messages_dict: 消息字典列表
            
        Returns:
            选中的工具名称列表
        """
        query_lower = user_query.lower()
        selected = []
        
        # 搜索相关关键词
        search_keywords = ["什么", "如何", "怎样", "查询", "搜索", "查找", "检索", "了解", "介绍", "定义", "最新", "分析"]
        if any(keyword in query_lower for keyword in search_keywords):
            if "web_search" in self.tool_manager.tools:
                selected.append("web_search")
        
        # 注意：已移除url_reader工具，博查搜索返回的摘要已经足够详细
        
        # 计算相关关键词
        calc_keywords = ["计算", "多少", "赔偿", "费用", "金额", "公式", "等于"]
        if any(keyword in query_lower for keyword in calc_keywords):
            if "python_executor" in self.tool_manager.tools:
                selected.append("python_executor")
            elif "calculator" in self.tool_manager.tools:
                selected.append("calculator")
        
        # 如果还是没有选择到工具，默认使用web_search（对于QA类任务）
        if not selected and "web_search" in self.tool_manager.tools:
            # 检查是否有系统提示词提到需要搜索
            for msg in messages_dict:
                if msg.get("role") == "system" and "搜索" in msg.get("content", ""):
                    selected.append("web_search")
                    break
        
        return selected
    
    def _generate_final_answer(self, recent_messages: List[Message]) -> str:
        """
        生成最终答案（当工具执行完成后）
        
        Args:
            recent_messages: 最近的消息列表
            
        Returns:
            最终答案文本
        """
        # 构建prompt
        system_prompt = """你是一个专业的助手。请根据用户的问题和工具执行结果，生成一个完整、准确的答案。
要求：
1. 答案要完整、准确
2. 如果工具执行结果中有相关信息，要充分利用
3. 如果信息不足，可以说明需要更多信息"""
        
        # 构建消息历史
        messages_dict = []
        for msg in recent_messages[-10:]:  # 只使用最近10条消息
            if isinstance(msg, Message):
                messages_dict.append(msg.to_dict())
            elif isinstance(msg, dict):
                messages_dict.append(msg)
        
        try:
            # 使用LLM生成最终答案
            response = self.llm.chat(
                messages=messages_dict,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            return response.strip() if response else ""
        except Exception as e:
            print(f"Warning: Failed to generate final answer: {e}")
            return ""

