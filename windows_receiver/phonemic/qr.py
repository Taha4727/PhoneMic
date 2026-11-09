"""Standard ISO/IEC 18004 compliant QR Code generator powered by Nayuki qrcodegen."""
from .qrcodegen import QrCode


def generate_qr_matrix(text: str) -> list[list[bool]]:
    """Encodes text into a 2D boolean matrix where True represents a dark module."""
    qr = QrCode.encode_text(text, QrCode.Ecc.LOW)
    size = qr.get_size()
    return [[qr.get_module(x, y) for x in range(size)] for y in range(size)]
