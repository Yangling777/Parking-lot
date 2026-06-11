"""Time synchronization module for ESP32 hardware.

Sends the current system time to the hardware via serial every 10 seconds
to keep the hardware clock in sync with the server.
"""

import time
import threading


def start_time_sync(ser):
    """Start a background daemon thread that sends system time over serial every 10s."""

    def sync_loop():
        while True:
            try:
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                ser.write((f"TIME|{current_time}\n").encode('utf-8'))
            except Exception as e:
                print(f"[Time Sync] Send error: {e}")
            time.sleep(10)

    t = threading.Thread(target=sync_loop, daemon=True)
    t.start()
    print("Time sync background service started.")
