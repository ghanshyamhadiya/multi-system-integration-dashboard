import logging
from collections import deque
from datetime import datetime

class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=50):
        super().__init__()
        self.log_records = deque(maxlen=capacity)

    def emit(self, record):
        # format record
        self.log_records.append({
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name
        })

memory_handler = MemoryLogHandler(capacity=50)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
memory_handler.setFormatter(formatter)

def get_logger(name):
    # init logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not any(isinstance(h, MemoryLogHandler) for h in logger.handlers):
        logger.addHandler(memory_handler)
        
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
    return logger

def get_recent_logs():
    # return logs
    return list(memory_handler.log_records)[::-1]
