"""Schema descriptors and their MemoryPack read/write implementations."""

from __future__ import annotations

import struct
from collections.abc import Sequence
from typing import Any

from .iota import decode_base_iota_id_potency, encode_base_iota_id_potency
from .mp import MemoryPackError, Reader, Writer


def _path(parent: str, name: str) -> str:
    return name if not parent else parent + "." + name


class Type:
    """Base class for a serializable type descriptor."""

    name = "?"

    def read(self, r: Reader, path: str = "") -> Any:
        raise NotImplementedError

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        raise NotImplementedError


PRIM_FORMATS = {
    "u8": ("<B", 1),
    "i8": ("<b", 1),
    "u16": ("<H", 2),
    "i16": ("<h", 2),
    "u32": ("<I", 4),
    "i32": ("<i", 4),
    "u64": ("<Q", 8),
    "i64": ("<q", 8),
    "f32": ("<f", 4),
    "f64": ("<d", 8),
}


class Prim(Type):
    def __init__(self, kind: str):
        self.kind = kind
        self.name = kind
        self.fmt, self.size = PRIM_FORMATS[kind]

    def read(self, r: Reader, path: str = "") -> Any:
        return struct.unpack(self.fmt, r.take(self.size))[0]

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        try:
            w.raw(struct.pack(self.fmt, value))
        except (struct.error, TypeError) as exc:
            raise MemoryPackError(
                f"{path}: cannot encode {value!r} as {self.kind} ({exc})"
            ) from exc


U8 = Prim("u8")
I8 = Prim("i8")
U16 = Prim("u16")
I16 = Prim("i16")
U32 = Prim("u32")
I32 = Prim("i32")
U64 = Prim("u64")
I64 = Prim("i64")
F32 = Prim("f32")
F64 = Prim("f64")


class Bool(Type):
    name = "bool"
    size = 1

    def read(self, r: Reader, path: str = "") -> bool:
        b = r.u8()
        if b not in (0, 1):
            raise MemoryPackError(
                f"{path}: invalid bool byte 0x{b:02X} at 0x{r.pos - 1:X}"
            )
        return bool(b)

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if isinstance(value, str):
            raise MemoryPackError(f"{path}: bool expected, got {value!r}")
        w.u8(1 if value else 0)


BOOL = Bool()


class Str(Type):
    name = "string"

    def read(self, r: Reader, path: str = "") -> str | None:
        try:
            return r.string()
        except MemoryPackError as exc:
            raise MemoryPackError(f"{path}: {exc}") from exc

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if value is not None and not isinstance(value, str):
            raise MemoryPackError(f"{path}: string expected, got {value!r}")
        w.string(value)


STRING = Str()


class Enum(Type):
    def __init__(self, name: str, underlying: Prim, members: dict[int, str]):
        self.name = name
        self.underlying = underlying
        self.size = underlying.size
        self.members = dict(members)
        self.by_name = {v: k for k, v in self.members.items()}

    def read(self, r: Reader, path: str = "") -> Any:
        raw = self.underlying.read(r)
        return self.members.get(raw, raw)

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if isinstance(value, str):
            if value not in self.by_name:
                raise MemoryPackError(f"{path}: unknown {self.name} name {value!r}")
            value = self.by_name[value]
        self.underlying.write(w, value)


class FixedArray(Type):
    """A C# fixed buffer of primitives (e.g. ``fixed int CardIds[5]``)."""

    def __init__(self, element: Type, count: int):
        self.element = element
        self.count = count
        self.size = element.size * count
        self.name = f"{element.name}[{count}]"

    def read(self, r: Reader, path: str = "") -> list[Any]:
        return [self.element.read(r, f"{path}[{i}]") for i in range(self.count)]

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if not isinstance(value, Sequence) or len(value) != self.count:
            raise MemoryPackError(
                f"{path}: expected {self.count} values, got {value!r}"
            )
        for i, item in enumerate(value):
            self.element.write(w, item, f"{path}[{i}]")


class IotaPackedField(Type):
    """``IotaInstance.BaseIotaIdPotency``, exposed as three flat JSON keys.

    The save stores one 32-bit value; in JSON it is unpacked to
    ``BaseIotaId``, ``Potency`` and ``TraitCount`` instead of an opaque number.
    """

    name = "BaseIotaIdPotency"
    size = 4
    flatten = True
    part_names = ("BaseIotaId", "Potency", "TraitCount")

    def read(self, r: Reader, path: str = "") -> dict[str, int]:
        decoded = decode_base_iota_id_potency(r.u32())
        out = {
            "BaseIotaId": decoded["BaseIotaId"],
            "Potency": decoded["Potency"],
            "TraitCount": decoded["TraitCount"],
        }
        if decoded["Reserved"]:
            out["Reserved"] = decoded["Reserved"]
        return out

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if not isinstance(value, dict):
            raise MemoryPackError(
                f"{path}: {self.name} expects an object, got {type(value).__name__!r}"
            )
        missing = [name for name in self.part_names if name not in value]
        if missing:
            raise MemoryPackError(
                f"{path}: {self.name} is missing {', '.join(missing)}"
            )
        packed = encode_base_iota_id_potency(
            value["BaseIotaId"], value["Potency"], value["TraitCount"]
        )
        reserved = value.get("Reserved", 0)
        if not 0 <= reserved <= 0x3FFF:
            raise MemoryPackError(f"{path}: Reserved must fit in 14 bits")
        w.u32(packed | (reserved << 18))


class UnmanagedStruct(Type):
    """A blittable struct: raw ``size`` bytes of memory, field offsets fixed."""

    def __init__(self, name: str, size: int, fields: Sequence[tuple[str, int, Type]]):
        self.name = name
        self.size = size
        self.fields = list(fields)
        covered = [False] * size
        last_end = 0
        for fname, offset, ftype in self.fields:
            fsize = getattr(ftype, "size", None)
            if fsize is None:
                raise ValueError(f"{name}.{fname} has no fixed size")
            if offset < last_end:
                raise ValueError(f"{name}.{fname} overlaps previous field")
            if offset + fsize > size:
                raise ValueError(f"{name}.{fname} exceeds struct size")
            for i in range(offset, offset + fsize):
                if covered[i]:
                    raise ValueError(f"{name}.{fname} overlaps a previous field")
                covered[i] = True
            last_end = offset + fsize
        self.gaps: list[tuple[int, int]] = []
        i = 0
        while i < size:
            if covered[i]:
                i += 1
                continue
            start = i
            while i < size and not covered[i]:
                i += 1
            self.gaps.append((start, i - start))

    def read(self, r: Reader, path: str = "") -> dict[str, Any]:
        raw = r.take(self.size)
        out: dict[str, Any] = {}
        for fname, offset, ftype in self.fields:
            sub = Reader(raw, offset)
            field_value = ftype.read(sub, _path(path, fname))
            if getattr(ftype, "flatten", False):
                out.update(field_value)
            else:
                out[fname] = field_value
        padding = {}
        for start, length in self.gaps:
            chunk = raw[start : start + length]
            if any(chunk):
                padding[str(start)] = chunk.hex()
        if padding:
            out["_padding"] = padding
        return out

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if not isinstance(value, dict):
            raise MemoryPackError(
                f"{path}: object expected for {self.name}, got {type(value).__name__!r}"
            )
        buf = bytearray(self.size)
        for fname, offset, ftype in self.fields:
            if getattr(ftype, "flatten", False):
                missing = [name for name in ftype.part_names if name not in value]
                if missing:
                    raise MemoryPackError(
                        f"{path}: missing field(s) "
                        f"{', '.join(repr(name) for name in missing)}"
                    )
                field_value = {name: value[name] for name in ftype.part_names}
                if "Reserved" in value:
                    field_value["Reserved"] = value["Reserved"]
            else:
                if fname not in value:
                    raise MemoryPackError(f"{path}: missing field {fname!r}")
                field_value = value[fname]
            tmp = Writer()
            ftype.write(tmp, field_value, _path(path, fname))
            data = tmp.getvalue()
            if len(data) != getattr(ftype, "size", len(data)):
                raise MemoryPackError(
                    f"{path}: {fname} wrote {len(data)} bytes, expected {ftype.size}"
                )
            buf[offset : offset + len(data)] = data
        pad = value.get("_padding")
        if pad:
            if not isinstance(pad, dict):
                raise MemoryPackError(
                    f"{path}: _padding must be an object of offset -> hex string"
                )
            by_start = {start: length for start, length in self.gaps}
            for key, chunk in pad.items():
                start = int(key)
                if start not in by_start:
                    raise MemoryPackError(
                        f"{path}: {self.name} has no padding gap at +{start}"
                    )
                length = by_start[start]
                raw = bytes.fromhex(chunk)
                if len(raw) != length:
                    raise MemoryPackError(
                        f"{path}: padding at +{start} must be {length} bytes"
                    )
                buf[start : start + length] = raw
        w.raw(bytes(buf))


class Object(Type):
    """A class or non-blittable struct with a member-count header."""

    def __init__(
        self,
        name: str,
        header: int,
        fields: Sequence[tuple[str, Type]],
        nullable: bool = True,
    ):
        self.name = name
        self.header = header
        self.fields = list(fields)
        self.nullable = nullable

    def read(self, r: Reader, path: str = "") -> dict[str, Any] | None:
        count = r.object_header()
        if count is None:
            if not self.nullable:
                raise MemoryPackError(
                    f"{path}: {self.name} is a struct and cannot be null"
                )
            return None
        if count != self.header:
            raise MemoryPackError(
                f"{path}: {self.name} header is {count} but schema expects "
                f"{self.header} (data version mismatch?)"
            )
        out: dict[str, Any] = {}
        for fname, ftype in self.fields:
            out[fname] = ftype.read(r, _path(path, fname))
        return out

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if value is None:
            if not self.nullable:
                raise MemoryPackError(
                    f"{path}: {self.name} is a struct and cannot be null"
                )
            w.null_object()
            return
        if not isinstance(value, dict):
            raise MemoryPackError(
                f"{path}: object expected for {self.name}, got {type(value).__name__!r}"
            )
        w.object_header(self.header)
        for fname, ftype in self.fields:
            if fname not in value:
                raise MemoryPackError(f"{path}: missing field {fname!r}")
            ftype.write(w, value[fname], _path(path, fname))


class ArrayOf(Type):
    """Array / List / HashSet: int32 count, then elements."""

    def __init__(self, element: Type, name: str | None = None):
        self.element = element
        self.name = name or f"{element.name}[]"

    def read(self, r: Reader, path: str = "") -> list[Any] | None:
        n = r.collection_header()
        if n is None:
            return None
        return [self.element.read(r, f"{path}[{i}]") for i in range(n)]

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if value is None:
            w.null_collection()
            return
        if isinstance(value, (dict, str, bytes)):
            raise MemoryPackError(f"{path}: array expected, got {value!r}")
        try:
            items = list(value)
        except TypeError as exc:
            raise MemoryPackError(f"{path}: array expected, got {value!r}") from exc
        w.collection_header(len(items))
        for i, item in enumerate(items):
            self.element.write(w, item, f"{path}[{i}]")


class DictOf(Type):
    """dictionary: int32 count, then key/value pairs in enumeration order."""

    def __init__(self, key: Type, value: Type):
        self.key = key
        self.value = value
        self.name = f"dictionary<{key.name},{value.name}>"

    def read(self, r: Reader, path: str = "") -> Any:
        n = r.collection_header()
        if n is None:
            return None
        pairs = []
        for i in range(n):
            k = self.key.read(r, f"{path}<{i}>.key")
            v = self.value.read(r, f"{path}<{i}>.value")
            pairs.append([k, v])
        if isinstance(self.key, Str):
            # JSON-friendly ordered mapping for string keys.
            return {k: v for k, v in pairs}
        return pairs

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if value is None:
            w.null_collection()
            return
        if isinstance(value, dict):
            pairs = list(value.items())
        else:
            pairs = [(p[0], p[1]) for p in value]
        w.collection_header(len(pairs))
        for i, (k, v) in enumerate(pairs):
            self.key.write(w, k, f"{path}<{i}>.key")
            self.value.write(w, v, f"{path}<{i}>.value")


class UnorderedList(Type):
    """``UnorderedListVal<T>`` / ``UnorderedListRef<T>`` (both are the same on the wire)."""

    def __init__(self, element: Type, ref: bool = False):
        self.element = element
        self.ref = ref
        self.name = f"UnorderedList{'Ref' if ref else 'Val'}<{element.name}>"

    def read(self, r: Reader, path: str = "") -> dict[str, Any] | None:
        count = r.object_header()
        if count is None:
            return None
        if count != 2:
            raise MemoryPackError(f"{path}: {self.name} header is {count}, expected 2")
        buf = ArrayOf(self.element, "buffer").read(r, _path(path, "buffer"))
        length = r.i32()
        return {"buffer": buf, "length": length}

    def write(self, w: Writer, value: Any, path: str = "") -> None:
        if value is None:
            w.null_object()
            return
        w.object_header(2)
        ArrayOf(self.element, "buffer").write(
            w, value.get("buffer"), _path(path, "buffer")
        )
        w.i32(value["length"])
