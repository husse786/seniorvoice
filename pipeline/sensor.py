"""PIR motion sensor (HC-SR501) on GPIO4 via lgpio (Pi 5 RP1 chip)."""

import time

try:
    import lgpio
except ImportError:
    lgpio = None

from config import PIR_GPIO_PIN, PIR_GPIO_CHIP
from logging_config import get_logger

log = get_logger("sensor")


def _check_lgpio():
    if lgpio is None:
        raise RuntimeError("lgpio not available. Install with: pip install lgpio")


def wait_for_motion() -> None:
    """Block until the PIR sensor detects motion on GPIO17."""
    _check_lgpio()

    h = lgpio.gpiochip_open(PIR_GPIO_CHIP)
    try:
        lgpio.gpio_claim_input(h, PIR_GPIO_PIN)
        log.info("Waiting for motion on GPIO%d (chip %d)...", PIR_GPIO_PIN, PIR_GPIO_CHIP)

        # Wait for HIGH signal
        while True:
            val = lgpio.gpio_read(h, PIR_GPIO_PIN)
            if val == 1:
                log.info("Motion detected!")
                return
            time.sleep(0.1)
    finally:
        lgpio.gpiochip_close(h)


def motion_detected() -> bool:
    """Non-blocking check: is motion currently detected?"""
    _check_lgpio()

    h = lgpio.gpiochip_open(PIR_GPIO_CHIP)
    try:
        lgpio.gpio_claim_input(h, PIR_GPIO_PIN)
        val = lgpio.gpio_read(h, PIR_GPIO_PIN)
        return val == 1
    finally:
        lgpio.gpiochip_close(h)
