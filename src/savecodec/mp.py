"""Low-level MemoryPack wire format used by the game.

The format was verified against the shipped serializers (IL2CPP code) and a
real save file.  Relevant points that differ from "textbook" MemoryPack:

* object header: one byte.  ``0xFF`` means null, otherwise the member count
  (0..249).  A zero member count is a valid, non-null object.
* collection header: a little-endian ``int32`` length.  ``-1`` means null.
* strings: ``int32`` header ``~utf8_byte_count`` (so it is negative), then an
  ``int32`` UTF-16 code-unit count, then the UTF-8 bytes.  Null is ``-1`` and
  the empty string is ``0`` (both only 4 bytes).
* unmanaged values/arrays: raw little-endian memory, no headers.  Arrays are
  ``int32`` element count followed by the raw elements.
"""

import struct


class MemoryPackError(Exception):
    """Raised when the byte stream does not match the expected schema."""


class Reader:
    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    # -- raw ---------------------------------------------------------------
    def take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.data):
            raise MemoryPackError(
                f"unexpected end of data: need {n} byte(s) at "
                f"0x{self.pos:X}, have {len(self.data) - self.pos}"
            )
        out = self.data[self.pos : end]
        self.pos = end
        return out

    def _unpack(self, fmt: str, size: int):
        return struct.unpack(fmt, self.take(size))[0]

    def u8(self) -> int:
        return self.take(1)[0]

    def i8(self) -> int:
        return self._unpack("<b", 1)

    def u16(self) -> int:
        return self._unpack("<H", 2)

    def i16(self) -> int:
        return self._unpack("<h", 2)

    def u32(self) -> int:
        return self._unpack("<I", 4)

    def i32(self) -> int:
        return self._unpack("<i", 4)

    def u64(self) -> int:
        return self._unpack("<Q", 8)

    def i64(self) -> int:
        return self._unpack("<q", 8)

    def f32(self) -> float:
        return self._unpack("<f", 4)

    def f64(self) -> float:
        return self._unpack("<d", 8)

    # -- MemoryPack headers ------------------------------------------------
    def object_header(self) -> int | None:
        """Return the member count, or None for a null object."""
        n = self.u8()
        if n == 0xFF:
            return None
        if n >= 0xFA:
            raise MemoryPackError(
                f"invalid object header 0x{n:02X} at 0x{self.pos - 1:X}"
            )
        return n

    def collection_header(self) -> int | None:
        n = self.i32()
        if n < -1:
            raise MemoryPackError(
                f"invalid collection length {n} at 0x{self.pos - 4:X}"
            )
        return None if n == -1 else n

    def string(self) -> str | None:
        head = self.i32()
        if head == -1:
            return None
        if head == 0:
            return ""
        if head > 0:
            raise MemoryPackError(f"invalid string header {head} at 0x{self.pos - 4:X}")
        utf8_len = ~head
        utf16_len = self.i32()
        raw = self.take(utf8_len)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MemoryPackError(
                f"invalid UTF-8 string at 0x{self.pos - utf8_len:X}: {exc}"
            ) from exc
        actual_len = len(text.encode("utf-16-le", "surrogatepass")) // 2
        if actual_len != utf16_len:
            raise MemoryPackError(
                f"string length mismatch at 0x{self.pos - utf8_len:X}: "
                f"header {utf16_len}, actual {actual_len}"
            )
        return text


class Writer:
    __slots__ = ("buf",)

    def __init__(self):
        self.buf = bytearray()

    def getvalue(self) -> bytes:
        return bytes(self.buf)

    def __len__(self) -> int:
        return len(self.buf)

    # -- raw ---------------------------------------------------------------
    def raw(self, data: bytes) -> None:
        self.buf += data

    def _pack(self, fmt: str, value) -> None:
        self.buf += struct.pack(fmt, value)

    def u8(self, v: int) -> None:
        self.buf.append(v & 0xFF)

    def i8(self, v: int) -> None:
        self._pack("<b", v)

    def u16(self, v: int) -> None:
        self._pack("<H", v)

    def i16(self, v: int) -> None:
        self._pack("<h", v)

    def u32(self, v: int) -> None:
        self._pack("<I", v)

    def i32(self, v: int) -> None:
        self._pack("<i", v)

    def u64(self, v: int) -> None:
        self._pack("<Q", v)

    def i64(self, v: int) -> None:
        self._pack("<q", v)

    def f32(self, v: float) -> None:
        self._pack("<f", v)

    def f64(self, v: float) -> None:
        self._pack("<d", v)

    # -- MemoryPack headers ------------------------------------------------
    def null_object(self) -> None:
        self.u8(0xFF)

    def object_header(self, member_count: int) -> None:
        if not 0 <= member_count < 0xFA:
            raise MemoryPackError(f"invalid member count {member_count}")
        self.u8(member_count)

    def null_collection(self) -> None:
        self.i32(-1)

    def collection_header(self, length: int) -> None:
        self.i32(length)

    def string(self, value: str | None) -> None:
        if value is None:
            self.i32(-1)
            return
        if value == "":
            self.i32(0)
            return
        raw = value.encode("utf-8")
        utf16_len = len(value.encode("utf-16-le", "surrogatepass")) // 2
        self.i32(~len(raw))
        self.i32(utf16_len)
        self.buf += raw
