import logging
import os
from typing import Union, Optional

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


def get_logger(name: str, level: Union[int, str, Optional[int]] = None,
               prefix: bool = True) \
        -> logging.Logger:
    level = level if level else LOG_LEVEL
    the_logger = logging.getLogger(name)
    the_logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    log_format = '%(levelname)s: %(message)s' if prefix else '%(message)s'
    handler.setFormatter(logging.Formatter(log_format))
    the_logger.addHandler(handler)
    return the_logger
