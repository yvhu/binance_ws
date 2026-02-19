"""
异步重试装饰器
提供指数退避重试机制，用于处理网络请求和API调用
"""

import asyncio
import functools
import logging
from typing import Callable, Optional, Type, Tuple, Any

logger = logging.getLogger(__name__)


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry_callback: Optional[Callable[[int, Exception], None]] = None
):
    """
    异步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数退避基数
        jitter: 是否添加随机抖动
        retry_on_exceptions: 需要重试的异常类型元组，None表示重试所有异常
        on_retry_callback: 重试时的回调函数，参数为(重试次数, 异常)
    
    Returns:
        装饰器函数
    
    Example:
        @async_retry(max_retries=3, base_delay=2.0)
        async def fetch_data():
            # 可能失败的操作
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否需要重试此异常
                    if retry_on_exceptions and not isinstance(e, retry_on_exceptions):
                        logger.error(f"Exception {type(e).__name__} not in retry list, not retrying")
                        raise
                    
                    # 如果是最后一次尝试，直接抛出异常
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries. "
                            f"Final error: {str(e)}"
                        )
                        raise
                    
                    # 计算延迟时间
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # 添加随机抖动（避免多个客户端同时重试）
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                        f"Error: {str(e)}. Retrying in {delay:.2f}s..."
                    )
                    
                    # 调用重试回调
                    if on_retry_callback:
                        try:
                            on_retry_callback(attempt + 1, e)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")
                    
                    # 等待后重试
                    await asyncio.sleep(delay)
            
            # 理论上不会到达这里，但为了类型检查
            raise last_exception
        
        return wrapper
    return decorator


class RetryableError(Exception):
    """可重试的异常基类"""
    pass


class NetworkError(RetryableError):
    """网络错误"""
    pass


class RateLimitError(RetryableError):
    """速率限制错误"""
    pass


class TemporaryError(RetryableError):
    """临时错误"""
    pass


def should_retry_exception(exception: Exception) -> bool:
    """
    判断异常是否应该重试
    
    Args:
        exception: 异常对象
    
    Returns:
        True表示应该重试，False表示不应该重试
    """
    # 可重试的异常类型
    retryable_types = (
        RetryableError,
        NetworkError,
        RateLimitError,
        TemporaryError,
        ConnectionError,
        TimeoutError,
    )
    
    # 检查异常类型
    if isinstance(exception, retryable_types):
        return True
    
    # 检查异常消息中的关键词
    error_message = str(exception).lower()
    retryable_keywords = [
        'timeout',
        'connection',
        'network',
        'rate limit',
        'temporary',
        'service unavailable',
        '503',
        '502',
        '504',
    ]
    
    for keyword in retryable_keywords:
        if keyword in error_message:
            return True
    
    return False

def sync_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry_callback: Optional[Callable[[int, Exception], None]] = None
):
    """
    同步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数退避基数
        jitter: 是否添加随机抖动
        retry_on_exceptions: 需要重试的异常类型元组，None表示重试所有异常
        on_retry_callback: 重试时的回调函数，参数为(重试次数, 异常)
    
    Returns:
        装饰器函数
    
    Example:
        @sync_retry(max_retries=3, base_delay=2.0)
        def fetch_data():
            # 可能失败的操作
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否需要重试此异常
                    if retry_on_exceptions and not isinstance(e, retry_on_exceptions):
                        logger.error(f"Exception {type(e).__name__} not in retry list, not retrying")
                        raise
                    
                    # 如果是最后一次尝试，直接抛出异常
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries. "
                            f"Final error: {str(e)}"
                        )
                        raise
                    
                    # 计算延迟时间
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # 添加随机抖动（避免多个客户端同时重试）
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                        f"Error: {str(e)}. Retrying in {delay:.2f}s..."
                    )
                    
                    # 调用重试回调
                    if on_retry_callback:
                        try:
                            on_retry_callback(attempt + 1, e)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")
                    
                    # 等待后重试
                    import time
                    time.sleep(delay)
            
            # 理论上不会到达这里，但为了类型检查
            raise last_exception
        
        return wrapper
    return decorator


def log_retry_attempt(attempt: int, exception: Exception):
    """
    记录重试尝试的回调函数
    
    Args:
        attempt: 当前尝试次数
        exception: 发生的异常
    """
    logger.warning(
        f"Retry attempt {attempt} due to: {type(exception).__name__}: {str(exception)}"
    )