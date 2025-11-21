"""Embedding模型，使用DashScope接口"""
import os
import time
from typing import List, Union
import dashscope
from http import HTTPStatus
import requests
from ..config.config import Config


class EmbeddingModel:
    """Embedding模型，用于将文本转换为向量（使用DashScope API）"""
    
    def __init__(self, config: Config):
        """
        初始化Embedding模型
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.model_name = config.embedding_model
        self.dimension = config.embedding_dim
        self.timeout = config.embedding_timeout
        self.max_retries = config.embedding_max_retries
        
        # 初始化DashScope API Key
        api_key = config.embedding_api_key or os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            dashscope.api_key = api_key
        else:
            raise ValueError("DashScope API key is required. Set embedding_api_key in config or DASHSCOPE_API_KEY environment variable.")
    
    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        将文本编码为向量（使用DashScope embedding API）
        
        Args:
            texts: 单个文本或文本列表
            
        Returns:
            单个向量或向量列表
        """
        # 确保texts是列表格式
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False
        
        # 调用DashScope embedding API，带重试机制
        last_exception = None
        delay = 1.0
        
        for attempt in range(self.max_retries + 1):
            try:
                # 设置超时（DashScope SDK可能不支持timeout参数，这里通过重试机制实现）
                start_time = time.time()
                
                # 尝试设置requests的超时（如果DashScope内部使用requests）
                # 注意：DashScope SDK可能不支持直接传递timeout，这里通过监控时间实现
                try:
                    resp = dashscope.TextEmbedding.call(
                        model=self.model_name,
                        input=texts
                    )
                except requests.exceptions.Timeout as e:
                    elapsed_time = time.time() - start_time
                    raise TimeoutError(f"Embedding API调用超时（{elapsed_time:.2f}秒 > {self.timeout}秒）: {str(e)}")
                
                # 检查是否超时
                elapsed_time = time.time() - start_time
                if elapsed_time > self.timeout:
                    raise TimeoutError(f"Embedding API调用超时（{elapsed_time:.2f}秒 > {self.timeout}秒）")
                
                # 检查响应状态
                if resp.status_code != HTTPStatus.OK:
                    raise RuntimeError(f"DashScope API error: {resp.message}")
                
                # 提取embedding向量
                embeddings = []
                if hasattr(resp, 'output') and resp.output:
                    # DashScope返回格式：resp.output.embeddings 或 resp.output['embeddings']
                    if hasattr(resp.output, 'embeddings'):
                        # 对象格式
                        for item in resp.output.embeddings:
                            if hasattr(item, 'embedding'):
                                embeddings.append(item.embedding)
                            elif isinstance(item, dict) and 'embedding' in item:
                                embeddings.append(item['embedding'])
                    elif isinstance(resp.output, dict) and 'embeddings' in resp.output:
                        # 字典格式
                        for item in resp.output['embeddings']:
                            if isinstance(item, dict) and 'embedding' in item:
                                embeddings.append(item['embedding'])
                            elif hasattr(item, 'embedding'):
                                embeddings.append(item.embedding)
                    elif isinstance(resp.output, list):
                        # 列表格式
                        for item in resp.output:
                            if isinstance(item, dict) and 'embedding' in item:
                                embeddings.append(item['embedding'])
                            elif hasattr(item, 'embedding'):
                                embeddings.append(item.embedding)
                            elif isinstance(item, list):
                                embeddings.append(item)
                
                if not embeddings:
                    raise RuntimeError("No embeddings returned from DashScope API")
                
                # 如果输入是单个文本，返回单个向量
                if single_text:
                    return embeddings[0]
                else:
                    return embeddings
            
            except (TimeoutError, RuntimeError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    # 等待后重试
                    time.sleep(delay)
                    delay *= 2.0  # 指数退避
                else:
                    # 最后一次尝试失败，抛出异常
                    raise RuntimeError(f"Embedding API调用失败（已重试{self.max_retries}次）: {str(e)}")
            except Exception as e:
                # 其他异常直接抛出
                raise RuntimeError(f"Error encoding texts with DashScope API: {str(e)}")
        
        # 理论上不会到达这里
        if last_exception:
            raise last_exception
    
    def get_dimension(self) -> int:
        """获取embedding维度"""
        return self.dimension
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name
