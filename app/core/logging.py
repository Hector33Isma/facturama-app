import logging
from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno
        logger_opt = logger.bind(request_id="app")
        logger_opt.log(level, record.getMessage())


def setup_logging() -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
    logger.add(
        "app.log",
        rotation="1 MB",
        retention="7 days",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        level="INFO",
    )
