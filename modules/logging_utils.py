import logging
import functools
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure the base logger with a file handler
logging.basicConfig(level=logging.INFO)

# Create a file handler
file_handler = RotatingFileHandler(
    'logs/application.log',  # Log file path
    maxBytes=10485760,       # 10MB
    backupCount=5            # Keep 5 backup files
)

# Set the format for the logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the root logger
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

def log_function_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get the logger for the module where the decorated function is defined
        logger = logging.getLogger(func.__module__)
        logger.info(f"Calling function: {func.__name__} with args: {args} and kwargs: {kwargs}")
        result = func(*args, **kwargs)
        logger.info(f"Function {func.__name__} returned: {result}")
        return result
    return wrapper

# Create and export a configured logger that can be imported directly
app_logger = logging.getLogger('app')