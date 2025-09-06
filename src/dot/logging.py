import logging
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET 
from rich.logging import RichHandler

LEVEL = INFO

def set_level(level: int):
    global LEVEL
    LEVEL = level
    logging.getLogger().setLevel(level)
    # Update all existing loggers
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.setLevel(level)

def get_logger(name: str = "dot") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = RichHandler(
            # show_time=False,
            show_level=False,
            show_path=False,
            markup=True,
            omit_repeated_times=False,
        )
        formatter = logging.Formatter(
            "%(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(LEVEL)
    return logger
