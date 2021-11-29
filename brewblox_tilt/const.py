import re
from pathlib import Path

CONFIG_DIR = Path('/share')
DEVICES_FILE_PATH = Path(CONFIG_DIR, 'devices.yml')
SG_CAL_FILE_PATH = Path(CONFIG_DIR, 'SGCal.csv')
TEMP_CAL_FILE_PATH = Path(CONFIG_DIR, 'tempCal.csv')

NORMALIZED_MAC_PATTERN = re.compile(r'^[A-F0-9]{12}$')
DEVICE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9 _\-\(\)\|]{1,100}$')
INVALID_NAME_CHAR_PATTERN = re.compile(r'[^a-zA-Z0-9 _\-\(\)\|]')

TILT_UUID_COLORS = {
    'a495bb10-c5b1-4b44-b512-1370f02d74de': 'Red',
    'a495bb20-c5b1-4b44-b512-1370f02d74de': 'Green',
    'a495bb30-c5b1-4b44-b512-1370f02d74de': 'Black',
    'a495bb40-c5b1-4b44-b512-1370f02d74de': 'Purple',
    'a495bb50-c5b1-4b44-b512-1370f02d74de': 'Orange',
    'a495bb60-c5b1-4b44-b512-1370f02d74de': 'Blue',
    'a495bb70-c5b1-4b44-b512-1370f02d74de': 'Yellow',
    'a495bb80-c5b1-4b44-b512-1370f02d74de': 'Pink'
}
