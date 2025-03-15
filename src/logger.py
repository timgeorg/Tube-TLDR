import logging
import sys

class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def create_logger(name: str, log_level: int = logging.INFO) -> logging.Logger:
        log: logging.Logger = logging.getLogger(name)
        log.setLevel(log_level)

        if not log.handlers:
            # Stream handler for console output
            stream_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
            stream_formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            stream_handler.setFormatter(stream_formatter)
            log.addHandler(stream_handler)

            # File handler for file output
            file_handler: logging.FileHandler = logging.FileHandler(f"{name}.log")
            file_formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            log.addHandler(file_handler)

        return log
