#!/usr/bin/env python3
"""PIR sensor calibration tool.

Run on the Pi while adjusting the HC-SR501 sensitivity & time-delay screws.
Shows real-time GPIO state, event counts, and timing so you can dial in
the right settings.

Usage:
    python test_pir.py            # default: GPIO17, gpiochip4
    python test_pir.py --pin 27   # different pin
    Ctrl+C to stop
"""

import argparse
import time
import lgpio

from config import PIR_GPIO_CHIP, PIR_GPIO_PIN


def main():
    parser = argparse.ArgumentParser(description="PIR sensor calibration tool")
    parser.add_argument("--pin", type=int, default=PIR_GPIO_PIN,
                        help=f"GPIO pin (default: {PIR_GPIO_PIN})")
    parser.add_argument("--chip", type=int, default=PIR_GPIO_CHIP,
                        help=f"GPIO chip (default: {PIR_GPIO_CHIP})")
    parser.add_argument("--interval", type=float, default=0.05,
                        help="Poll interval in seconds (default: 0.05)")
    args = parser.parse_args()

    h = lgpio.gpiochip_open(args.chip)
    lgpio.gpio_claim_input(h, args.pin)

    print(f"PIR Calibration — GPIO{args.pin} on gpiochip{args.chip}")
    print(f"Poll interval: {args.interval}s")
    print()
    print("HC-SR501 screws:")
    print("  Left  (Sx) = Sensitivity  — CW = more sensitive")
    print("  Right (Tx) = Hold time    — CW = longer hold (min ~2.5s)")
    print()
    print("Waiting for sensor to settle (5s warm-up)...")
    time.sleep(5)
    print("Ready. Adjust screws and observe output. Ctrl+C to quit.\n")

    trigger_count = 0
    prev = 0
    rise_time = None

    try:
        while True:
            val = lgpio.gpio_read(h, args.pin)

            # Rising edge: LOW → HIGH
            if val == 1 and prev == 0:
                trigger_count += 1
                rise_time = time.time()
                print(f"  ▲ MOTION  #{trigger_count}  "
                      f"[{time.strftime('%H:%M:%S')}]")

            # Falling edge: HIGH → LOW
            if val == 0 and prev == 1:
                hold = time.time() - rise_time if rise_time else 0
                print(f"  ▼ clear   #{trigger_count}  "
                      f"held {hold:.1f}s  "
                      f"[{time.strftime('%H:%M:%S')}]")

            prev = val
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\nDone. Total triggers: {trigger_count}")
    finally:
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
