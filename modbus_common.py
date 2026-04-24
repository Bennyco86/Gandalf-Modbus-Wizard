"""
Common Modbus utilities for Gandalf Modbus Wizard.
Supports:
- Integers (16/32/64 bit, signed/unsigned)
- Floats (32/64 bit)
- ASCII Strings (Read & Write)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Tuple
import math
import struct


# --- display formatting ---
FLOAT_FIXED_DECIMALS = 3     
FLOAT_SCI_SIG_DIGITS = 6     
FLOAT_SCI_HIGH = 1e6         
FLOAT_SCI_LOW = 1e-3         

def _format_float(v: float) -> str:
    try:
        fv = float(v)
    except Exception:
        return "n/a"

    if not math.isfinite(fv): return str(fv)
    if fv == 0.0: return f"{0.0:.{FLOAT_FIXED_DECIMALS}f}"

    av = abs(fv)
    if av >= FLOAT_SCI_HIGH or av < FLOAT_SCI_LOW:
        return f"{fv:.{FLOAT_SCI_SIG_DIGITS}e}"

    return f"{fv:.{FLOAT_FIXED_DECIMALS}f}"


class SwapMode(str, Enum):
    NONE = "none"
    WORD = "word"
    BYTE = "byte"
    WORD_AND_BYTE = "word_and_byte"


# Number of 16-bit registers required per type
TYPE_REGISTER_WIDTH = {
    "int16": 1, "uint16": 1,
    "int32": 2, "uint32": 2,
    "int64": 4, "uint64": 4,
    "float32": 2, "float64": 4,
    # String Types (2 chars per register)
    "string10": 5,   # 10 chars
    "string20": 10,  # 20 chars
    "string32": 16,  # 32 chars
    "string64": 32,  # 64 chars
}

TYPE_BIT_WIDTH = {
    "int16": 16, "uint16": 16,
    "int32": 32, "uint32": 32,
    "int64": 64, "uint64": 64,
}


@dataclass(frozen=True)
class ExceptionInfo:
    code: Optional[int]
    name: Optional[str]
    message: str


_EXCEPTION_NAMES = {
    1: "Illegal Function",
    2: "Illegal Data Address",
    3: "Illegal Data Value",
    4: "Slave Device Failure",
}


def exception_status_text(exc: Optional[ExceptionInfo], undefined: bool) -> str:
    if exc is None:
        return "OK" if not undefined else "undefined"
    if exc.code is None:
        return exc.message or ("undefined" if undefined else "Error")
    name = exc.name or _EXCEPTION_NAMES.get(exc.code, "Exception")
    return f"E{exc.code:02d} {name}"


def parse_exception_from_response(response: Any, fallback_message: str) -> ExceptionInfo:
    if response is None:
        return ExceptionInfo(code=None, name=None, message=fallback_message)

    try:
        is_err = bool(getattr(response, "isError")())
    except Exception:
        is_err = False

    if not is_err:
        return ExceptionInfo(code=None, name=None, message="OK")

    code = getattr(response, "exception_code", None)
    if isinstance(code, int):
        return ExceptionInfo(code=code, name=_EXCEPTION_NAMES.get(code), message=fallback_message)

    s = str(response) if response is not None else ""
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
    """
    type_name = (type_name or "").lower().strip()
    if type_name not in TYPE_REGISTER_WIDTH:
        return None, "n/a"

    needed = TYPE_REGISTER_WIDTH[type_name]
    if len(words) != needed:
        return None, "n/a"

    # --- STRING HANDLING ---
    if type_name.startswith("string"):
        # Apply Byte Swaps first
        if swap_mode in (SwapMode.BYTE, SwapMode.WORD_AND_BYTE):
             words = [_apply_byte_swap_to_word(w) for w in words]
        
        # Strings are rarely Word Swapped, but if requested:
        if swap_mode in (SwapMode.WORD, SwapMode.WORD_AND_BYTE):
             words = list(reversed(words))

        try:
            chars = bytearray()
            for w in words:
                chars.extend(struct.pack(">H", w & 0xFFFF))
            
            # Decode ASCII, stop at first null terminator
            full_str = chars.decode('ascii', errors='replace')
            if '\x00' in full_str:
                clean_str = full_str.split('\x00')[0]
            else:
                clean_str = full_str
            return clean_str, clean_str
        except Exception:
            return None, "Err"

    # --- NUMERIC HANDLING ---
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


def _swap_words_list(words: List[int], mode: SwapMode) -> List[int]:
    if mode in (SwapMode.WORD, SwapMode.WORD_AND_BYTE):
        words = list(reversed(words))
    
    if mode in (SwapMode.BYTE, SwapMode.WORD_AND_BYTE):
        words = [_apply_byte_swap_to_word(w) for w in words]
        
    return words

def encode_value_to_words(value: Any, type_name: str, swap_mode: SwapMode) -> List[int]:
    """
    Encodes a Python value (int, float, or string) into 16-bit integers.
    """
    type_name = (type_name or "").lower().strip()
    if type_name not in TYPE_REGISTER_WIDTH:
        return []

    # 1. Handle Strings
    if type_name.startswith("string"):
        try:
            input_str = str(value)
            input_bytes = input_str.encode('ascii', errors='replace')
        except:
            return []

        # Pad with \x00 to reach required length
        num_regs = TYPE_REGISTER_WIDTH[type_name]
        total_bytes = num_regs * 2
        
        if len(input_bytes) > total_bytes:
            input_bytes = input_bytes[:total_bytes]
        else:
            input_bytes += b'\x00' * (total_bytes - len(input_bytes))
            
        # Convert bytes to words
        words = []
        for i in range(0, total_bytes, 2):
            w = int.from_bytes(input_bytes[i:i+2], byteorder='big')
            words.append(w)
            
        # Swap logic for strings (usually only Byte swap matters)
        if swap_mode in (SwapMode.WORD, SwapMode.WORD_AND_BYTE):
             words = list(reversed(words))
        if swap_mode in (SwapMode.BYTE, SwapMode.WORD_AND_BYTE):
             words = [_apply_byte_swap_to_word(w) for w in words]
             
        return words

    # 2. Handle Integers
    if "int" in type_name and "float" not in type_name:
        bits = TYPE_BIT_WIDTH.get(type_name, 16)
        try:
            val_int = int(value)
        except:
            return []
            
        if val_int < 0:
            val_int = (1 << bits) + val_int
            
        mask = (1 << bits) - 1
        val_int &= mask
        
        num_regs = TYPE_REGISTER_WIDTH[type_name]
        raw_bytes = val_int.to_bytes(num_regs * 2, byteorder='big')
        words = []
        for i in range(0, len(raw_bytes), 2):
            words.append(int.from_bytes(raw_bytes[i:i+2], byteorder='big'))
            
        return _swap_words_list(words, swap_mode)

    # 3. Handle Floats
    try:
        val_float = float(value)
    except:
        return []

    if type_name == "float32":
        b = struct.pack(">f", val_float)
        w1 = int.from_bytes(b[0:2], byteorder='big')
        w2 = int.from_bytes(b[2:4], byteorder='big')
        return _swap_words_list([w1, w2], swap_mode)

    if type_name == "float64":
        b = struct.pack(">d", val_float)
        words = []
        for i in range(0, 8, 2):
            words.append(int.from_bytes(b[i:i+2], byteorder='big'))
        return _swap_words_list(words, swap_mode)

    return []