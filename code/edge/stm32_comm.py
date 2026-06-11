import re
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class GateCommand(Enum):
    OPEN = "GATE_OPEN"
    CLOSE = "GATE_CLOSE"
    STOP = "GATE_STOP"
    QUERY = "GATE_QUERY"


class LedMode(Enum):
    OFF = "LED_OFF"
    GREEN = "LED_GREEN"
    RED = "LED_RED"
    YELLOW = "LED_YELLOW"
    BLINK_GREEN = "LED_BLINK_GREEN"
    BLINK_RED = "LED_BLINK_RED"


class SensorType(Enum):
    ULTRASONIC = "HC_SR04"
    INFRARED = "IR_OBSTACLE"
    MAGNETIC = "GEO_MAGNETIC"


@dataclass
class Stm32Command:
    cmd: str
    params: dict = field(default_factory=dict)
    seq: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class Stm32Response:
    cmd: str
    status: str
    data: dict = field(default_factory=dict)
    seq: int = 0
    timestamp: float = field(default_factory=time.time)


class Stm32Protocol:
    FRAME_HEADER = b'\xAA\x55'
    FRAME_FOOTER = b'\x55\xAA'
    CMD_SENSOR_REPORT = 0x01
    CMD_GATE_CONTROL = 0x02
    CMD_LED_CONTROL = 0x03
    CMD_SERVO_CONTROL = 0x04
    CMD_HEARTBEAT = 0x05
    CMD_ACK = 0x0F

    @staticmethod
    def pack_frame(cmd_id: int, data: bytes) -> bytes:
        length = len(data)
        payload = bytes([cmd_id, (length >> 8) & 0xFF, length & 0xFF]) + data
        checksum = sum(payload) & 0xFF
        return Stm32Protocol.FRAME_HEADER + payload + bytes([checksum]) + Stm32Protocol.FRAME_FOOTER

    @staticmethod
    def unpack_frame(raw: bytes) -> Optional[tuple]:
        if len(raw) < 8 or raw[:2] != Stm32Protocol.FRAME_HEADER:
            return None
        if raw[-2:] != Stm32Protocol.FRAME_FOOTER:
            return None
        payload = raw[2:-3]
        checksum = raw[-3]
        if sum(payload) & 0xFF != checksum:
            return None
        cmd_id = payload[0]
        length = (payload[1] << 8) | payload[2]
        data = payload[3:3 + length]
        return cmd_id, data


class Stm32SensorParser:
    @staticmethod
    def parse_ultrasonic(data: bytes) -> dict:
        if len(data) >= 4:
            slot_id = data[0]
            distance_high = data[1]
            distance_low = data[2]
            occupied_flag = data[3]
            distance = (distance_high << 8) | distance_low
            return {
                "slot_number": f"A-{slot_id:03d}",
                "distance_cm": round(distance / 10.0, 1),
                "occupied": bool(occupied_flag),
                "sensor_type": "HC_SR04"
            }
        return {}

    @staticmethod
    def build_gate_command(cmd: GateCommand, params: dict = None) -> bytes:
        cmd_map = {GateCommand.OPEN: 0x01, GateCommand.CLOSE: 0x00,
                   GateCommand.STOP: 0x02, GateCommand.QUERY: 0x03}
        code = cmd_map.get(cmd, 0x03)
        gate_id = (params or {}).get('gate_id', 1)
        angle = (params or {}).get('angle', 0)
        return bytes([gate_id, code, angle])

    @staticmethod
    def build_led_command(mode: LedMode, params: dict = None) -> bytes:
        led_map = {LedMode.OFF: 0x00, LedMode.GREEN: 0x01, LedMode.RED: 0x02,
                   LedMode.YELLOW: 0x03, LedMode.BLINK_GREEN: 0x11, LedMode.BLINK_RED: 0x12}
        code = led_map.get(mode, 0x00)
        slot_id = (params or {}).get('slot_id', 1)
        blink_interval = (params or {}).get('blink_interval', 500)
        return bytes([slot_id, code, (blink_interval >> 8) & 0xFF, blink_interval & 0xFF])


class Stm32VirtualEmulator:
    def __init__(self, num_slots=100):
        self.num_slots = num_slots
        self.slots = {}
        self.gates = {}
        self.leds = {}
        self._init_hardware()
        self.running = False
        self.emulate_thread = None

    def _init_hardware(self):
        for i in range(1, self.num_slots + 1):
            slot = f"A-{i:03d}"
            self.slots[slot] = {"occupied": False, "distance": 300.0}
            self.gates[slot] = {"state": "closed", "angle": 0}
            self.leds[slot] = {"mode": "off"}

    def start_emulation(self, callback: Callable = None):
        self.running = True
        self.emulate_thread = threading.Thread(
            target=lambda: self._emulate_loop(callback), daemon=True
        )
        self.emulate_thread.start()

    def stop_emulation(self):
        self.running = False

    def _emulate_loop(self, callback: Callable = None):
        import random
        while self.running:
            for slot_num, slot_data in self.slots.items():
                if random.random() < 0.02:
                    slot_data["occupied"] = not slot_data["occupied"]
                    slot_data["distance"] = random.uniform(10, 50) if slot_data["occupied"] else random.uniform(100, 300)
                    sensor_data = {
                        "slot_number": slot_num,
                        "distance_cm": round(slot_data["distance"], 1),
                        "occupied": slot_data["occupied"],
                        "gate_state": self.gates.get(slot_num, {}).get("state", "closed"),
                        "timestamp": time.time()
                    }
                    if callback:
                        callback(sensor_data)
            time.sleep(0.5)

    def process_command(self, raw: bytes) -> Optional[bytes]:
        result = Stm32Protocol.unpack_frame(raw)
        if result is None:
            return None
        cmd_id, data = result

        if cmd_id == Stm32Protocol.CMD_GATE_CONTROL:
            gate_id = data[0]
            code = data[1]
            gate_key = f"A-{gate_id:03d}"
            if code == 0x01:
                self.gates[gate_key] = {"state": "open", "angle": 90}
            elif code == 0x00:
                self.gates[gate_key] = {"state": "closed", "angle": 0}
            return Stm32Protocol.pack_frame(
                Stm32Protocol.CMD_ACK,
                bytes([gate_id, code, 0x00])
            )

        elif cmd_id == Stm32Protocol.CMD_LED_CONTROL:
            slot_id = data[0]
            code = data[1]
            led_key = f"A-{slot_id:03d}"
            mode_names = {0x00: "off", 0x01: "green", 0x02: "red", 0x03: "yellow",
                         0x11: "blink_green", 0x12: "blink_red"}
            self.leds[led_key] = {"mode": mode_names.get(code, "off")}
            return Stm32Protocol.pack_frame(
                Stm32Protocol.CMD_ACK,
                bytes([slot_id, code, 0x00])
            )

        elif cmd_id == Stm32Protocol.CMD_HEARTBEAT:
            return Stm32Protocol.pack_frame(
                Stm32Protocol.CMD_ACK,
                bytes([0x00, 0x00, 0x00])
            )

        return None
