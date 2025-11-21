"""重试工具函数"""
import time
from typing import Callable, Any, Optional, Type
from functools import wraps


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    带指数退避的重试装饰器
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数（可选）
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        # 最后一次尝试失败，抛出异常
                        raise last_exception
            
            # 理论上不会到达这里
            raise last_exception
        
        return wrapper
    return decorator


def retry_on_timeout(
    max_retries: int = 3,
    timeout: float = 30.0,
    exceptions: tuple = (TimeoutError, ConnectionError, Exception)
):
    """
    针对超时错误的重试装饰器
    
    Args:
        max_retries: 最大重试次数
        timeout: 超时时间（秒）
        exceptions: 需要重试的异常类型
    
    Returns:
        装饰器函数
    """
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=2.0,
        backoff_factor=1.5,
        exceptions=exceptions
    )

