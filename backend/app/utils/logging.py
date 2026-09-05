"""
Logging configuration.

TODO (Backend Dev):
- Configure structured logging
- Add request ID tracking
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("packsure")
