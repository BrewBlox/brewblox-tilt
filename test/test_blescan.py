"""
Tests brewblox_tilt.blescan
"""

from binascii import unhexlify

from brewblox_tilt import blescan

TESTED = blescan.__name__


def test_b2string():
    assert blescan.b2string(bytes([0x00, 0xff])) == '00ff'
    assert blescan.b2string(bytes([0x00, 0xff]), ':') == '00:ff'
    assert blescan.b2string(bytes([])) == ''


def test_b2number():
    assert blescan.b2number(bytes([0x00, 0xff]), False) == 255
    assert blescan.b2number(bytes([0x00, 0xff]), True) == 255
    assert blescan.b2number(bytes([0x80, 0xff]), False) == 33023
    assert blescan.b2number(bytes([0x80, 0xff]), True) == -32513


def test_read_packet():
    invalid = b'043e2802010201b8bc0699974a1c03039ffe17169ffe0000000000000000000000000000000000000000b2'
    valid = b'043e2a020103011e14fc977fdd1e0201041aff4c000215a495bb40c5b14b44b5121370f02d74de0045042206bc'

    assert blescan.read_packet(unhexlify('')) is None
    assert blescan.read_packet(unhexlify(invalid)) is None
    assert blescan.read_packet(unhexlify(valid)) == blescan.TiltEventData(
        mac='dd:7f:97:fc:14:1e',
        uuid='a495bb40c5b14b44b5121370f02d74de',
        major=69,
        minor=1058,
        txpower=6,
        rssi=-68,
    )
