"""系统配置文件"""
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class Config:
    """系统配置类"""
    
    # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
    llm_provider: str = "openai"  # openai, anthropic等
    llm_model: str = "qwen-max"  # DashScope模型
    llm_api_key: Optional[str] = "sk-5d4975fe68f24d83809ac3c7bf7468ba"  # 默认API key
    llm_base_url: Optional[str] = None  # DashScope兼容端点
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout: float = 120.0  # LLM API调用超时时间（秒）- 增加到120秒
    llm_max_retries: int = 3  # LLM API调用最大重试次数
    
    # Embedding配置（使用DashScope接口）
    embedding_model: str = "text-embedding-v4"  # DashScope embedding model
    embedding_dim: int = 1024  # DashScope embedding dimension (text-embedding-v4返回1024维)
    embedding_api_key: Optional[str] = "sk-5d4975fe68f24d83809ac3c7bf7468ba"  # 默认API key（与LLM相同）
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
    bocha_api_key: Optional[str] = "sk-abc3ef836fd9487c867cc58df5f76c31"  # 博查API Key（默认值，建议使用环境变量）
    python_executor_timeout: int = 30
    
    # Self-reflection配置
    reflection_enabled: bool = True
    reflection_roles: list = None  # 不同角色的prompt
    
    def __post_init__(self):
        """初始化后处理"""
        # LLM配置（使用OpenAI接口连接到DashScope兼容端点）
        # 环境变量优先，如果没有环境变量则使用默认值
        env_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if env_key:
            self.llm_api_key = env_key
        # 如果既没有环境变量，也没有显式设置，则使用默认值（已在字段定义中设置）
        
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # Embedding配置（使用DashScope接口）
        # 环境变量优先，如果没有环境变量则使用llm_api_key或默认值
        env_embedding_key = os.getenv("DASHSCOPE_API_KEY")
        if env_embedding_key:
            self.embedding_api_key = env_embedding_key
        elif self.embedding_api_key is None:
            # 如果没有设置embedding_api_key，使用llm_api_key（它们通常是同一个key）
            self.embedding_api_key = self.llm_api_key
        
        if self.reflection_roles is None:
            self.reflection_roles = ["critic", "improver", "validator"]
        
        # 博查API Key配置（环境变量优先）
        if not self.bocha_api_key or self.bocha_api_key == "sk-abc3ef836fd9487c867cc58df5f76c31":
            env_bocha_key = os.getenv("BOCHA_API_KEY")
            if env_bocha_key:
                self.bocha_api_key = env_bocha_key

