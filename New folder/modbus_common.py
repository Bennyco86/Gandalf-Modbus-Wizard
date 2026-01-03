"""
Common Modbus utilities for Gandalf Modbus Wizard.

This module is intentionally UI-free and client-free:
- No tkinter imports
- No pymodbus imports

It provides:
- Swap modes (word/byte/both)
- Supported data types and register widths
- Exception parsing helpers (works with pymodbus response objects when available)
- A shared decode pipeline (int16/32/64, uint, float32/64)

Float display:
- Shows fixed decimals for normal ranges (e.g. 1073.058)
- Automatically switches to scientific notation for very large/small values to avoid
  massive strings (e.g. 1.234567e+150).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Tuple
import math
import struct


# --- display formatting ---
FLOAT_FIXED_DECIMALS = 3     # normal float formatting (e.g. 1073.058)
FLOAT_SCI_SIG_DIGITS = 6     # scientific notation precision (mantissa digits)
FLOAT_SCI_HIGH = 1e6         # switch to scientific if abs(value) >= this
FLOAT_SCI_LOW = 1e-3         # switch to scientific if 0 < abs(value) < this


def _format_float(v: float) -> str:
    """Format floats compactly while keeping decimals for "normal" values."""
    try:
        fv = float(v)
    except Exception:
        return "n/a"

    if not math.isfinite(fv):
        # inf / nan
        return str(fv)

    if fv == 0.0:
        return f"{0.0:.{FLOAT_FIXED_DECIMALS}f}"

    av = abs(fv)
    if av >= FLOAT_SCI_HIGH or av < FLOAT_SCI_LOW:
        # Use scientific to prevent huge strings like 1713460186...etc
        # Example: 1.234567e+150
        return f"{fv:.{FLOAT_SCI_SIG_DIGITS}e}"

    return f"{fv:.{FLOAT_FIXED_DECIMALS}f}"


class SwapMode(str, Enum):
    NONE = "none"
    WORD = "word"
    BYTE = "byte"
    WORD_AND_BYTE = "word_and_byte"


# Number of 16-bit registers required per type
TYPE_REGISTER_WIDTH = {
    "int16": 1,
    "uint16": 1,
    "int32": 2,
    "uint32": 2,
    "int64": 4,
    "uint64": 4,
    "float32": 2,
    "float64": 4,
}

# Bit widths for integer types (used for binary/hex formatting)
TYPE_BIT_WIDTH = {
    "int16": 16,
    "uint16": 16,
    "int32": 32,
    "uint32": 32,
    "int64": 64,
    "uint64": 64,
}


@dataclass(frozen=True)
class ExceptionInfo:
    code: Optional[int]          # Modbus exception code (1..255) when known
    name: Optional[str]          # Human readable name if known
    message: str                 # Detail for logs/UI


_EXCEPTION_NAMES = {
    1: "Illegal Function",
    2: "Illegal Data Address",
    3: "Illegal Data Value",
    4: "Slave Device Failure",
}


def exception_status_text(exc: Optional[ExceptionInfo], undefined: bool) -> str:
    """Turns an exception into the short UI status text."""
    if exc is None:
        return "OK" if not undefined else "undefined"
    if exc.code is None:
        return exc.message or ("undefined" if undefined else "Error")
    name = exc.name or _EXCEPTION_NAMES.get(exc.code, "Exception")
    return f"E{exc.code:02d} {name}"


def parse_exception_from_response(response: Any, fallback_message: str) -> ExceptionInfo:
    """
    Best-effort mapping from a pymodbus response object (or None) to ExceptionInfo.

    Handles:
    - response.isError() for pymodbus responses
    - response.exception_code when present
    - str(response) fallback
    """
    if response is None:
        return ExceptionInfo(code=None, name=None, message=fallback_message)

    try:
        # Many pymodbus response objects provide isError()
        is_err = bool(getattr(response, "isError")())
    except Exception:
        is_err = False

    if not is_err:
        return ExceptionInfo(code=None, name=None, message="OK")

    code = getattr(response, "exception_code", None)
    if isinstance(code, int):
        return ExceptionInfo(code=code, name=_EXCEPTION_NAMES.get(code), message=fallback_message)

    # Some versions include exception info in string repr
    s = str(response) if response is not None else ""
    # Heuristic parse "Illegal Data Address" etc
    for c, n in _EXCEPTION_NAMES.items():
        if n.lower() in s.lower():
            return ExceptionInfo(code=c, name=n, message=fallback_message)

    return ExceptionInfo(code=None, name=None, message=s or fallback_message)


def _apply_byte_swap_to_word(word: int) -> int:
    word &= 0xFFFF
    return ((word & 0x00FF) << 8) | ((word & 0xFF00) >> 8)


def _apply_swaps(words: List[int], mode: SwapMode) -> List[int]:
    out = [int(w) & 0xFFFF for w in words]

    if mode in (SwapMode.BYTE, SwapMode.WORD_AND_BYTE):
        out = [_apply_byte_swap_to_word(w) for w in out]

    if mode in (SwapMode.WORD, SwapMode.WORD_AND_BYTE):
        out = list(reversed(out))

    return out


def decode_register_words(words: List[int], type_name: str, swap_mode: SwapMode) -> Tuple[Optional[Any], str]:
    """
    Decode raw 16-bit words to a python value.
    Returns (value, display_text).

    Notes:
    - swap_mode applies only to multi-register types. For 1-register types it's ignored.
    - For floats we decode IEEE-754 using big-endian byte order after swaps.
    """
    type_name = (type_name or "").lower().strip()
    if type_name not in TYPE_REGISTER_WIDTH:
        return None, "n/a"

    needed = TYPE_REGISTER_WIDTH[type_name]
    if len(words) != needed:
        return None, "n/a"

    if needed == 1:
        w = int(words[0]) & 0xFFFF
        if type_name == "int16":
            v = struct.unpack(">h", struct.pack(">H", w))[0]
            return v, str(v)
        if type_name == "uint16":
            return w, str(w)
        return None, "n/a"

    w2 = _apply_swaps(words, swap_mode)
    b = bytearray()
    for w in w2:
        b.extend(struct.pack(">H", int(w) & 0xFFFF))

    try:
        if type_name == "int32":
            v = struct.unpack(">i", bytes(b))[0]
            return v, str(v)
        if type_name == "uint32":
            v = struct.unpack(">I", bytes(b))[0]
            return v, str(v)
        if type_name == "int64":
            v = struct.unpack(">q", bytes(b))[0]
            return v, str(v)
        if type_name == "uint64":
            v = struct.unpack(">Q", bytes(b))[0]
            return v, str(v)
        if type_name == "float32":
            v = struct.unpack(">f", bytes(b))[0]
            return v, _format_float(v)
        if type_name == "float64":
            v = struct.unpack(">d", bytes(b))[0]
            return v, _format_float(v)
    except Exception:
        return None, "n/a"

    return None, "n/a"
