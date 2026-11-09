"""Protocol, audio and application constants (wire protocol is unchanged from v0.8)."""

VERSION = "0.11.0"
APP_NAME = "PhoneMic Receiver"

# --- Network / wire protocol (must match PhoneMicService.kt) -----------------
DEFAULT_PORT = 5001
PACKET_MAGIC = b"PM01"            # 'PM01' + uint32 big-endian seq + 16-bit LE mono PCM (48 kHz)
PACKET_MAGIC_48K = b"PM01"
PACKET_MAGIC_24K = b"PM02"        # 24 kHz Balanced (240 samples = 480 bytes)
PACKET_MAGIC_16K = b"PM03"        # 16 kHz Low-Bandwidth (160 samples = 320 bytes)
DISCOVERY_PROBE = b"PM_DISCOVER"
DISCOVERY_REPLY = b"PMA1"         # reply / beacon: b"PMA1 <version> <ip>"
CMD_PAUSE = b"PMP1"
CMD_RESUME = b"PMR1"
SIO_UDP_CONNRESET = 0x9800000C    # stop Windows turning ICMP port-unreachable into recv errors

# --- Audio ---------------------------------------------------------------------
SAMPLE_RATE = 48000
FRAME = 480                       # samples per packet (10 ms)
PCM_BYTES = FRAME * 2
FRAME_MS = 1000.0 * FRAME / SAMPLE_RATE

CABLE_HINT = "CABLE Input"
VB_CABLE_URL = "https://vb-audio.com/Cable/"

# --- Misc ------------------------------------------------------------------------
STREAM_TIMEOUT_S = 1.5            # no packets for this long == stream considered gone
MUTEX_NAME = "Local\\PhoneMicReceiverSingleInstance"
INSTANCE_PORT = 47511             # loopback only: a second launch asks the running copy to show its window
