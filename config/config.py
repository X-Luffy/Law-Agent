"""系统配置文件"""
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class Config:
    """系统配置类"""
    
    # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
    llm_provider: str = "openai"  # openai, anthropic等
    llm_model: str = "qwen3-max"  # DashScope模型
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None  # DashScope兼容端点
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout: float = 120.0  # LLM API调用超时时间（秒）- 增加到120秒
    llm_max_retries: int = 3  # LLM API调用最大重试次数
    
    # Embedding配置（使用DashScope接口）
    embedding_model: str = "text-embedding-v4"  # DashScope embedding model
    embedding_dim: int = 1024  # DashScope embedding dimension (text-embedding-v4返回1024维)
    embedding_api_key: Optional[str] = None
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
    web_search_max_results: int = 5
    python_executor_timeout: int = 30
    
    # Self-reflection配置
    reflection_enabled: bool = True
    reflection_roles: list = None  # 不同角色的prompt
    
    def __post_init__(self):
        """初始化后处理"""
        # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
        if self.llm_api_key is None:
            self.llm_api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # Embedding配置（使用DashScope接口）
        if self.embedding_api_key is None:
            self.embedding_api_key = os.getenv("DASHSCOPE_API_KEY") or self.llm_api_key  # 默认使用相同的API key
        
        if self.reflection_roles is None:
            self.reflection_roles = ["critic", "improver", "validator"]

