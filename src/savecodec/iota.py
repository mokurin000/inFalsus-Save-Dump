"""Packing of ``IotaInstance.BaseIotaIdPotency``.

The save field is **not** an iota ID.  It is a 32-bit bitfield:

======  ==========================================================
bits    meaning
======  ==========================================================
0..1    ``TraitCountRaw`` = ``3 - TraitCount`` (0..3)
2..11   ``Potency`` (10 bits, 0..1023)
12..17  ``BaseIotaId`` (6 bits, 0..63; only 0..40 are used)
18..31  reserved / always 0 in observed saves
======  ==========================================================

This matches the IL2CPP getters in ``GameAssembly.dll``::

    get_TraitCountRaw()  =>  value & 3
    get_Potency()        => (value >> 2)  & 0x3FF
    get_BaseIotaId()     => (value >> 12) & 0x3F
    GetDefaultTuple()    => (base << 12) | (potency << 2) | (~traitCount & 3)

Examples from the supplied save::

    8635  (0x21BB) -> BaseIotaId=2,  Potency=110, TraitCount=0
    33211 (0x81BB) -> BaseIotaId=8,  Potency=110, TraitCount=0
"""

BASE_IOTA_ID_BITS = 6
POTENCY_BITS = 10
TRAIT_COUNT_BITS = 2

BASE_IOTA_ID_MAX = (1 << BASE_IOTA_ID_BITS) - 1  # 63
POTENCY_MAX = (1 << POTENCY_BITS) - 1  # 1023
TRAIT_COUNT_MAX = (1 << TRAIT_COUNT_BITS) - 1  # 3


def decode_base_iota_id_potency(value: int) -> dict[str, int]:
    """Split a ``BaseIotaIdPotency`` value into its fields.

    ``value`` may be the signed ``int`` seen in C# or an unsigned 32-bit
    value; both are reduced to 32 bits first.
    """
    value &= 0xFFFFFFFF
    raw = value & TRAIT_COUNT_MAX
    return {
        "BaseIotaId": (value >> 12) & BASE_IOTA_ID_MAX,
        "Potency": (value >> 2) & POTENCY_MAX,
        "TraitCountRaw": raw,
        "TraitCount": TRAIT_COUNT_MAX - raw,
        "Reserved": value >> 18,
    }


def encode_base_iota_id_potency(
    base_iota_id: int, potency: int, trait_count: int
) -> int:
    """Build the packed value written to ``BaseIotaIdPotency``."""
    if not 0 <= base_iota_id <= BASE_IOTA_ID_MAX:
        raise ValueError(f"base_iota_id must be 0..{BASE_IOTA_ID_MAX}")
    if not 0 <= potency <= POTENCY_MAX:
        raise ValueError(f"potency must be 0..{POTENCY_MAX}")
    if not 0 <= trait_count <= TRAIT_COUNT_MAX:
        raise ValueError(f"trait_count must be 0..{TRAIT_COUNT_MAX}")
    return (
        ((base_iota_id & BASE_IOTA_ID_MAX) << 12)
        | ((potency & POTENCY_MAX) << 2)
        | ((TRAIT_COUNT_MAX - trait_count) & TRAIT_COUNT_MAX)
    )
