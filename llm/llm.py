"""LLM模块，使用OpenAI接口连接到DashScope兼容端点"""
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from openai import APITimeoutError, APIError
from ..config.config import Config
from ..schema import Message
from ..utils.retry import retry_on_timeout


class LLM:
    """LLM类，使用OpenAI接口连接到DashScope兼容端点"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化LLM
        
        Args:
            config: 系统配置
        """
        self.config = config or Config()
        
        # 初始化OpenAI客户端（连接到DashScope兼容端点）
        api_key = self.config.llm_api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = self.config.llm_base_url or os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.model = self.config.llm_model
        self.temperature = self.config.llm_temperature
        self.max_tokens = self.config.llm_max_tokens
        self.timeout = self.config.llm_timeout
        self.max_retries = self.config.llm_max_retries
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        进行对话
        
        Args:
            messages: 消息列表（OpenAI格式）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大token数（可选）
            stream: 是否流式输出（可选）
            
        Returns:
            LLM回复内容
        """
        # 构建消息列表
        chat_messages = []
        
        # 添加系统提示词
        if system_prompt:
            chat_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加对话消息
        for msg in messages:
            if isinstance(msg, Message):
                # 转换为OpenAI格式
                chat_messages.append(msg.to_dict())
            elif isinstance(msg, dict):
                chat_messages.append(msg)
            else:
                raise ValueError(f"Unsupported message type: {type(msg)}")
        
        # 调用OpenAI API（连接到DashScope兼容端点），带重试机制
        @retry_on_timeout(max_retries=self.max_retries, timeout=self.timeout)
        def _call_api():
            if stream:
                # 流式输出
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=chat_messages,
                    temperature=temperature or self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                    stream=True,
                    timeout=self.timeout
                )
                
                # 收集流式输出
                content = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                
                return content
            else:
                # 非流式输出
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=chat_messages,
                    temperature=temperature or self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                    timeout=self.timeout
                )
                
                # 提取回复内容
                return response.choices[0].message.content
        
        try:
            return _call_api()
        except (APITimeoutError, TimeoutError) as e:
            raise TimeoutError(f"LLM API调用超时（{self.timeout}秒）: {str(e)}")
        except APIError as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"LLM调用出错: {str(e)}")
    
    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        进行带工具的对话
        
        Args:
            messages: 消息列表
            tools: 工具列表（OpenAI格式）
            tool_choice: 工具选择模式（"auto", "none", "required"）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大token数（可选）
            
        Returns:
            包含content和tool_calls的字典
        """
        # 构建消息列表
        chat_messages = []
        
        # 添加系统提示词
        if system_prompt:
            chat_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加对话消息
        for msg in messages:
            if isinstance(msg, Message):
                chat_messages.append(msg.to_dict())
            elif isinstance(msg, dict):
                chat_messages.append(msg)
            else:
                raise ValueError(f"Unsupported message type: {type(msg)}")
        
        # 构建请求参数
        request_params = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens
        }
        
        # 添加工具相关参数
        if tools:
            request_params["tools"] = tools
        
        if tool_choice:
            request_params["tool_choice"] = tool_choice
        
        # 调用OpenAI API（连接到DashScope兼容端点），带重试机制
        @retry_on_timeout(max_retries=self.max_retries, timeout=self.timeout)
        def _call_api():
            return self.client.chat.completions.create(
                **request_params,
                timeout=self.timeout
            )
        
        try:
            response = _call_api()
        except (APITimeoutError, TimeoutError) as e:
            raise TimeoutError(f"LLM API调用超时（{self.timeout}秒）: {str(e)}")
        except APIError as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"LLM调用出错: {str(e)}")
        
        # 提取回复内容
        result = {
            "content": response.choices[0].message.content,
            "tool_calls": None
        }
        
        # 提取工具调用
        if response.choices[0].message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in response.choices[0].message.tool_calls
            ]
        
        return result
