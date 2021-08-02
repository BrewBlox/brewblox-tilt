import struct
from dataclasses import dataclass
from typing import List, Optional

import bluetooth._bluetooth as bluez
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)

OGF_LE_CTL = 0x08
OCF_LE_SET_SCAN_ENABLE = 0x000C

LE_META_EVENT = 0x3E
LE_ADVERTISING_REPORT = 0x02
TILT_PARAM_LENGTH = 42
TILT_EVENT_LENGTH = 45  # BLE header bytes + params

# The first bytes for tilt events are static.
# We can use them to sanity check incoming data.
TILT_HEADER = bytes([
    bluez.HCI_EVENT_PKT,
    LE_META_EVENT,
    TILT_PARAM_LENGTH,
    LE_ADVERTISING_REPORT
])


@dataclass
class TiltEventData:
    mac: str
    uuid: str
    major: int
    minor: int
    txpower: int
    rssi: int


def b2string(pkt: bytes, sep: str = ...) -> str:
    # bytes.hex() only supports a `sep` argument in python >= 3.8
    s = bytes.hex(pkt)
    if sep is ...:
        return s
    else:
        return sep.join(s[i:i+2] for i in range(0, len(s), 2))


def b2number(pkt: bytes, signed: bool) -> int:
    return int.from_bytes(pkt, byteorder='big', signed=signed)


def read_packet(pkt: bytes) -> Optional[TiltEventData]:
    # Packets use the BLE iBeacon spec,
    # {idx} [{value}] {description}
    #
    # 00 [04] HCI opcode (constant, 0x04 -> HCI event)
    # 01 [3E] LE event (constant)
    # 02 [2A] Parameter total length (constant, 42)
    # 03 [02] LE sub-event code (constant, 0x02 -> advertising report)
    # 04 [01] Number of reports (1)
    # 05 [03] Event type
    # 06 [01] Public address type
    # 07 [??] MAC address start
    # ...
    # 12 [??] MAC address end
    # 13 [1E] ??????
    # 14 [02] Header length (constant, 2)
    # 15 [01] Flag data type
    # 16 [04] LE flags
    # 17 [1A] Data length (constant, 26)
    # 18 [FF] Data type
    # 19 [4C] manufacturer ID - Apple iBeacon
    # 20 [00] manufacturer ID - Apple iBeacon
    # 21 [02] type (constant, defined by iBeacon spec)
    # 22 [15] length (constant, defined by iBeacon spec)
    # 23 [??] device UUID start
    # ...
    # 38 [??] device UUID end
    # 39 [??] major - temperature (degF)
    # 40 [??] major - temperature (degF)
    # 41 [??] minor - specific gravity (scaled to integer)
    # 42 [??] minor - specific gravity (scaled to integer)
    # 43 [??] TX power (dBm)
    # 44 [??] RSSI (dBm)

    if len(pkt) == TILT_EVENT_LENGTH and pkt[:4] == TILT_HEADER:
        return TiltEventData(
            mac=b2string(pkt[7:13][::-1], ':'),
            uuid=b2string(pkt[23:39]),
            major=b2number(pkt[39:41], False),
            minor=b2number(pkt[41:43], False),
            txpower=b2number(pkt[43:44], True),
            rssi=b2number(pkt[44:45], True),
        )


def hci_toggle_le_scan(sock, enable: bool):
    cmd_pkt = struct.pack('<BB', int(enable), 0x00)
    bluez.hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)


def open_socket():
    sock = bluez.hci_open_dev(0)
    hci_toggle_le_scan(sock, True)
    return sock


def scan(sock, loop_count=100) -> List[TiltEventData]:
    old_filter = sock.getsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, 14)

    # perform a device inquiry on bluetooth device #0
    # before the inquiry is performed, bluez should flush its cache of
    # previously discovered devices
    flt = bluez.hci_filter_new()
    bluez.hci_filter_all_events(flt)
    bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
    sock.setsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, flt)

    output: List[TiltEventData] = []

    for _ in range(0, loop_count):
        pkt = sock.recv(255)
        data = read_packet(pkt)

        if data:
            output.append(data)

    sock.setsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, old_filter)
    return output
