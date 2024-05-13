import asyncio
import logging
import os
import sys

from emu import Emu2

logger = logging.getLogger(__name__)
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, log_level, logging.INFO),
    format="[%(asctime)s] %(levelname)s %(message)s"
)

emu2 = Emu2()

if __name__ == "__main__":
    try:
        asyncio.run(emu2.tasks())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info('Exited emu2mqtt')
