"""LLM模块，使用OpenAI接口连接到DashScope兼容端点"""
import os
from typing import List, Dict, Any, Optional

# 处理不同版本的openai包
try:
    # 尝试新版本 (>=1.0.0)
    from openai import OpenAI
    from openai import APITimeoutError, APIError
    OPENAI_NEW_VERSION = True
except ImportError:
    try:
        # 旧版本 (<1.0.0) 使用不同的API
        import openai
        OpenAI = None
        OPENAI_NEW_VERSION = False
        # 旧版本使用 openai.ChatCompletion 等
        APITimeoutError = Exception
        APIError = openai.OpenAIError if hasattr(openai, 'OpenAIError') else Exception
    except ImportError:
        raise ImportError("需要安装 openai 包")

# 处理相对导入问题
try:
    from ..config.config import Config
    from ..schema import Message
    from ..utils.retry import retry_on_timeout
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config
    from schema import Message
    # 使用明确的路径避免与eval/utils.py冲突
    # 使用 importlib 明确导入项目根目录下的 utils.retry
    import importlib.util
    retry_path = project_root / "utils" / "retry.py"
    if retry_path.exists():
        # 使用绝对路径加载，避免与 eval/utils.py 冲突
        spec = importlib.util.spec_from_file_location("utils_retry_module", retry_path)
        utils_retry_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils_retry_module)
        retry_on_timeout = utils_retry_module.retry_on_timeout
    else:
        # 如果文件不存在，尝试直接导入（此时应该已经在 sys.path 中）
        try:
            from utils.retry import retry_on_timeout
        except ImportError:
            # 如果还是失败，尝试使用 importlib.import_module
            import importlib
            utils_retry = importlib.import_module("utils.retry")
            retry_on_timeout = utils_retry.retry_on_timeout


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
        # 优先使用config中的值，如果没有则从环境变量获取
        self.api_key = (
            self.config.llm_api_key or 
            os.getenv('DASHSCOPE_API_KEY') or 
            os.getenv('OPENAI_API_KEY')
        )
        self.base_url = (
            self.config.llm_base_url or 
            os.getenv('BASE_URL') or 
            os.getenv('OPENAI_BASE_URL') or 
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 根据openai版本初始化客户端
        if OPENAI_NEW_VERSION:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            # 旧版本：设置全局配置
            import openai
            openai.api_key = self.api_key
            openai.api_base = self.base_url
            self.client = None
        
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
            if OPENAI_NEW_VERSION:
                # 新版本API
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
            else:
                # 旧版本API
                import openai
                if stream:
                    # 流式输出（旧版本可能不支持）
                    response = openai.ChatCompletion.create(
                        model=self.model,
                        messages=chat_messages,
                        temperature=temperature or self.temperature,
                        max_tokens=max_tokens or self.max_tokens,
                        stream=True
                    )
                    
                    # 收集流式输出
                    content = ""
                    for chunk in response:
                        if chunk.choices[0].delta.get('content'):
                            content += chunk.choices[0].delta['content']
                    
                    return content
                else:
                    # 非流式输出
                    response = openai.ChatCompletion.create(
                        model=self.model,
                        messages=chat_messages,
                        temperature=temperature or self.temperature,
                        max_tokens=max_tokens or self.max_tokens
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
            if OPENAI_NEW_VERSION:
                return self.client.chat.completions.create(
                    **request_params,
                    timeout=self.timeout
                )
            else:
                # 旧版本API
                import openai
                return openai.ChatCompletion.create(**request_params)
        
        try:
            response = _call_api()
        except (APITimeoutError, TimeoutError) as e:
            raise TimeoutError(f"LLM API调用超时（{self.timeout}秒）: {str(e)}")
        except APIError as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"LLM调用出错: {str(e)}")
        
        # 提取回复内容
        if OPENAI_NEW_VERSION:
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
        else:
            # 旧版本API
            result = {
                "content": response.choices[0].message.content,
                "tool_calls": None
            }
            
            # 旧版本可能不支持tool_calls，需要检查
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tool_call.get("id", ""),
                        "type": tool_call.get("type", "function"),
                        "function": {
                            "name": tool_call.get("function", {}).get("name", ""),
                            "arguments": tool_call.get("function", {}).get("arguments", "")
                        }
                    }
                    for tool_call in response.choices[0].message.tool_calls
                ]
        
        return result
