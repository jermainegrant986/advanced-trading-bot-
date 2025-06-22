import time
import logging

def retry(max_retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.warning(f"Attempt {attempt+1} failed in {func.__name__}: {e}")
                    time.sleep(delay * (2 ** attempt))
            logging.error(f"Max retries reached for {func.__name__}")
            return None
        return wrapper
    return decorator
