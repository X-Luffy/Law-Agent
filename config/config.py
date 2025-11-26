"""系统配置文件"""
import os
from typing import Optional
from dataclasses import dataclass


def _find_api_key_from_env(key_name: str = None) -> Optional[str]:
    """从环境变量中查找API key（通过sk-前缀模糊匹配）
    
    Args:
        key_name: 特定的环境变量名（如DASHSCOPE_API_KEY），如果为None则搜索所有环境变量
        
    Returns:
        找到的API key，如果没找到则返回None
    """
    if key_name:
        # 如果指定了环境变量名，直接查找
        key = os.getenv(key_name)
        if key and key.startswith("sk-"):
            return key
        return None
    
    # 否则搜索所有环境变量，查找以"sk-"开头的值
    for env_var, value in os.environ.items():
        if value and isinstance(value, str) and value.startswith("sk-"):
            # 优先查找常见的API key环境变量名
            if any(keyword in env_var.upper() for keyword in ["API_KEY", "KEY", "TOKEN", "SECRET"]):
                return value
    
    return None


@dataclass
class Config:
    """系统配置类"""
    
    # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
    llm_provider: str = "openai"  # openai, anthropic等
    llm_model: str = "qwen-max"  # DashScope模型
    llm_api_key: Optional[str] = None  # API key（必须从环境变量或参数传入）
    llm_base_url: Optional[str] = None  # DashScope兼容端点
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout: float = 120.0  # LLM API调用超时时间（秒）- 增加到120秒
    llm_max_retries: int = 3  # LLM API调用最大重试次数
    
    # Embedding配置（使用DashScope接口）
    embedding_model: str = "text-embedding-v4"  # DashScope embedding model
    embedding_dim: int = 1024  # DashScope embedding dimension (text-embedding-v4返回1024维)
    embedding_api_key: Optional[str] = None  # API key（必须从环境变量或参数传入）
    embedding_timeout: float = 300.0  # Embedding API调用超时时间（秒）- 增加到300秒
    embedding_max_retries: int = 3  # Embedding API调用最大重试次数
    
    # 向量数据库配置
    vector_db_path: str = "./data/vector_db"
    vector_db_collection: str = "long_term_memory"
    
    # 上下文配置
    context_window_size: int = 10  # 保留最近N轮对话
    context_refine_threshold: int = 5  # 超过N轮后开始精炼
    
    # 记忆配置
    session_memory_size: int = 50  # session记忆大小
    long_term_memory_top_k: int = 5  # 检索长期记忆的top-k
    
    # 工具配置
    web_search_max_results: int = 8  # 博查搜索默认返回8条结果
    bocha_api_key: Optional[str] = None  # 博查API Key（必须从环境变量或参数传入）
    python_executor_timeout: int = 30
    
    # Self-reflection配置
    reflection_enabled: bool = True
    reflection_roles: list = None  # 不同角色的prompt
    
    def __post_init__(self):
        """初始化后处理"""
        # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
        # 优先从环境变量中查找API key
        if not self.llm_api_key:
            # 按优先级查找：DASHSCOPE_API_KEY > OPENAI_API_KEY > LLM_API_KEY > 模糊匹配
            self.llm_api_key = (
                _find_api_key_from_env("DASHSCOPE_API_KEY") or
                _find_api_key_from_env("OPENAI_API_KEY") or
                _find_api_key_from_env("LLM_API_KEY") or
                _find_api_key_from_env()
            )
        
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # Embedding配置（使用DashScope接口）
        # 优先从环境变量中查找API key
        if not self.embedding_api_key:
            # 按优先级查找：DASHSCOPE_API_KEY > 模糊匹配 > 使用llm_api_key
            self.embedding_api_key = (
                _find_api_key_from_env("DASHSCOPE_API_KEY") or
                _find_api_key_from_env() or
                self.llm_api_key
            )
        
        if self.reflection_roles is None:
            self.reflection_roles = ["critic", "improver", "validator"]
        
        # 博查API Key配置（从环境变量中查找）
        if not self.bocha_api_key:
            self.bocha_api_key = (
                _find_api_key_from_env("BOCHA_API_KEY") or
                _find_api_key_from_env()
            )

