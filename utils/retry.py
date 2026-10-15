"""Bounded exponential backoff and retry utilities."""

import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """Decorator to retry flaky I/O or API calls with bounded exponential backoff and jitter."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = initial_delay
            last_exception = None

            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logger.warning(
                            f"Function {func.__name__} failed on final attempt {attempt}/{retries}: {e}"
                        )
                        raise

                    jitter = random.uniform(0.0, 0.5 * current_delay)
                    sleep_time = min(current_delay + jitter, max_delay)
                    logger.info(
                        f"Retry {attempt}/{retries} for {func.__name__} after {sleep_time:.2f}s due to: {e}"
                    )
                    time.sleep(sleep_time)
                    current_delay = min(current_delay * backoff_factor, max_delay)

            if last_exception:
                raise last_exception

        return wrapper
    return decorator
