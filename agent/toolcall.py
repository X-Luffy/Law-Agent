"""ToolCallAgent类"""
from typing import List, Dict, Any, Optional
from .react import ReActAgent
from ..tools.tool_manager import ToolManager
from ..tools.base import BaseTool
from ..embedding.tool_selector import ToolSelector
from ..schema import AgentState, Memory, Message
from ..config.config import Config
from ..llm.llm import LLM


class ToolCallAgent(ReActAgent):
    """ToolCallAgent，继承ReActAgent，添加可用工具集合，实现think和act方法"""
    
    def __init__(
        self,
        name: str = "toolcall_agent",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 30,
        available_tools: Optional[List[BaseTool]] = None,
        tool_manager: Optional[ToolManager] = None
    ):
        """
        初始化ToolCallAgent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数
            available_tools: 可用工具列表
            tool_manager: 工具管理器
        """
        super().__init__(
            name=name,
            description=description or "An agent that can execute tool calls",
            system_prompt=system_prompt,
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
        
        # 初始化工具选择器
        self.tool_selector = ToolSelector(self.config)
        
        # 嵌入工具描述
        tool_descriptions = self.tool_manager.get_all_tool_descriptions()
        self.tool_selector.embed_tool_descriptions(tool_descriptions)
        
        # 初始化LLM（用于生成工具参数）
        self.llm = LLM(self.config)
        
        # 当前工具调用
        self.current_tool_calls: List[Dict[str, Any]] = []
        
        # 当前用户查询（供工具执行时使用）
        self.current_user_query: str = ""
    
    async def think(self) -> bool:
        """
        思考阶段：决定使用哪些工具
        
        Returns:
            是否需要执行行动
        """
        # 获取最近的对话上下文
        recent_messages = self.memory.get_recent_messages(10)
        
        # 构建用户查询（从最近的用户消息中提取）
        user_query = ""
        for msg in reversed(recent_messages):
            if isinstance(msg, Message):
                if msg.role == "user" and msg.content:
                    user_query = msg.content
                    break
            elif isinstance(msg, dict):
                if msg.get("role") == "user" and msg.get("content"):
                    user_query = msg.get("content")
                    break
        
        if not user_query:
            return False
        
        # 保存用户查询到实例变量，供act方法使用
        self.current_user_query = user_query
        
        # 使用embedding模型进行工具选择
        # 将用户query进行embedding，与现有tool的description进行相似度计算
        # 转换recent_messages为字典格式
        messages_dict = []
        for msg in recent_messages:
            if isinstance(msg, Message):
                messages_dict.append(msg.to_dict())
            elif isinstance(msg, dict):
                messages_dict.append(msg)
        
        selected_tools = self.tool_selector.select_tools(
            user_query,
            context={"messages": messages_dict},
            top_k=3
        )
        
        # 准备工具调用
        self.current_tool_calls = []
        for tool_name in selected_tools:
            tool = self.tool_manager.get_tool(tool_name)
            if tool:
                # 使用LLM生成工具调用的参数
                tool_args = self._generate_tool_arguments(tool_name, user_query, recent_messages)
                tool_call = {
                    "id": f"call_{len(self.current_tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": tool_args
                    }
                }
                self.current_tool_calls.append(tool_call)
        
        # 记录思考过程
        if self.current_tool_calls:
            self.update_memory(
                "assistant",
                f"Selected tools: {[tc['function']['name'] for tc in self.current_tool_calls]}",
                tool_calls=self.current_tool_calls
            )
            return True
        
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
        for tool_call in self.current_tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            # 获取工具实例
            tool = self.tool_manager.get_tool(tool_name)
            if not tool:
                results.append(f"Error: Tool '{tool_name}' not found")
                continue
            
            try:
                # 执行工具
                # TODO: 解析tool_args为字典
                import json
                args_dict = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                
                # 构建上下文
                context = {
                    "messages": [msg.to_dict() for msg in self.memory.get_recent_messages(10)],
                    "max_results": args_dict.get("max_results", 5)
                }
                
                # 从参数中提取用户输入（工具可能需要的关键词、URL等）
                # 优先从args_dict中获取query、url、city等参数
                tool_input = args_dict.get("query") or args_dict.get("url") or args_dict.get("city") or args_dict.get("input") or self.current_user_query
                
                # 执行工具
                result = tool.execute(user_input=tool_input, context=context)
                
                # 记录工具执行结果
                self.update_memory(
                    "tool",
                    str(result),
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
                
                results.append(f"Tool '{tool_name}' executed: {result}")
            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                results.append(error_msg)
                self.update_memory(
                    "tool",
                    error_msg,
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
        
        # 清空当前工具调用
        self.current_tool_calls = []
        
        return "\n".join(results)
    
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

