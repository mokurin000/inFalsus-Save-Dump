import json
import os
import unittest

from savecodec import (
    decode,
    decode_base_iota_id_potency,
    encode,
    encode_base_iota_id_potency,
    to_json,
)
from savecodec.mp import MemoryPackError, Reader, Writer
from savecodec.schema import SavedDeck

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE = os.path.join(ROOT, "tests", "test.sav")
IOTAS = os.path.join(ROOT, "data", "iota.json")


class StringFormatTests(unittest.TestCase):
    def roundtrip(self, value):
        w = Writer()
        w.string(value)
        r = Reader(w.getvalue())
        self.assertEqual(r.string(), value)
        self.assertEqual(r.pos, len(w.getvalue()))
        return w.getvalue()

    def test_null(self):
        self.assertEqual(self.roundtrip(None), b"\xff\xff\xff\xff")

    def test_empty(self):
        self.assertEqual(self.roundtrip(""), b"\x00\x00\x00\x00")

    def test_ascii(self):
        raw = self.roundtrip("cyaegha")
        self.assertEqual(raw[:4], (-8).to_bytes(4, "little", signed=True))
        self.assertEqual(raw[4:8], (7).to_bytes(4, "little", signed=True))
        self.assertEqual(raw[8:], b"cyaegha")

    def test_cjk(self):
        raw = self.roundtrip("\u65e5\u672c\u8a9e")
        # 9 UTF-8 bytes, 3 UTF-16 code units
        self.assertEqual(raw[:4], (-10).to_bytes(4, "little", signed=True))
        self.assertEqual(raw[4:8], (3).to_bytes(4, "little", signed=True))
        self.assertEqual(len(raw), 17)

    def test_surrogate_pair(self):
        raw = self.roundtrip("\U0001f600")
        # 4 UTF-8 bytes, 2 UTF-16 code units
        self.assertEqual(raw[:4], (-5).to_bytes(4, "little", signed=True))
        self.assertEqual(raw[4:8], (2).to_bytes(4, "little", signed=True))


class PaddingTests(unittest.TestCase):
    def test_nonzero_padding_roundtrip(self):
        value = {
            "CardIds": [1, 2, 3, 4, 5],
            "Assigned": True,
            "_padding": {"21": "aabbcc"},
        }
        w = Writer()
        SavedDeck.write(w, value)
        self.assertEqual(len(w.getvalue()), 24)
        self.assertEqual(w.getvalue()[21:24], b"\xaa\xbb\xcc")
        r = Reader(w.getvalue())
        decoded = SavedDeck.read(r)
        self.assertEqual(decoded["_padding"], {"21": "aabbcc"})
        self.assertEqual(r.pos, 24)

    def test_zero_padding_is_implicit(self):
        value = {"CardIds": [1, 2, 3, 4, 5], "Assigned": False}
        w = Writer()
        SavedDeck.write(w, value)
        self.assertEqual(w.getvalue()[21:24], b"\x00\x00\x00")
        decoded = SavedDeck.read(Reader(w.getvalue()))
        self.assertNotIn("_padding", decoded)


class SaveRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAVE):
            raise unittest.SkipTest("savestate_V3.sav not present")
        with open(SAVE, "rb") as fh:
            cls.data = fh.read()
        cls.save = decode(cls.data)

    def test_counts(self):
        s = self.save
        self.assertEqual(s["CardInventory"]["allCards"]["length"], 55)
        self.assertEqual(len(s["CardInventory"]["EncounterIdToSavedDeck"]), 105)
        self.assertEqual(s["IotaInventory"]["allIota"]["length"], 390)
        self.assertEqual(len(s["GameResults"]["highscores"]), 56)
        self.assertEqual(s["GameResults"]["history"]["length"], 83)
        self.assertEqual(s["EncounterResults"]["results"]["length"], 46)
        self.assertEqual(len(s["StoryToState"]["storyToState"]), 215)
        self.assertEqual(len(s["RecipeSaveState"]["saveData"]), 42)
        self.assertEqual(s["LootDropState"]["dropStates"]["length"], 74)

    def test_binary_roundtrip(self):
        self.assertEqual(encode(self.save), self.data)

    def test_json_roundtrip(self):
        restored = json.loads(to_json(self.save))
        self.assertEqual(encode(restored), self.data)

    def test_known_values(self):
        card = self.save["CardInventory"]["allCards"]["buffer"][0]
        self.assertEqual(card["CardId"], 101)
        self.assertEqual(card["CardBaseId"], 39)
        self.assertEqual(card["CardColorType"], "Blue")
        self.assertEqual(card["BasePower"], 6999.0)
        self.assertEqual(self.save["GeneralSaveState"]["SelectedCharacter"], "Ayame")
        key, value = self.save["StoryToState"]["storyToState"][0]
        self.assertEqual(key, 416876656)
        self.assertEqual(value["StoryIdentifier"], 416876656)

    def test_edit_and_reencode(self):
        save = json.loads(to_json(self.save))
        save["CardInventory"]["allCards"]["buffer"][0]["BasePower"] = 1234.5
        save["GeneralSaveState"]["LastSelectedPackId"] = 7
        data = encode(save)
        self.assertEqual(len(data), len(self.data))
        again = decode(data)
        self.assertEqual(
            again["CardInventory"]["allCards"]["buffer"][0]["BasePower"], 1234.5
        )
        self.assertEqual(again["GeneralSaveState"]["LastSelectedPackId"], 7)

    def test_unused_fields_are_padding(self):
        card = self.save["CardInventory"]["allCards"]["buffer"][0]
        self.assertEqual([k for k in card if k.startswith("Unused")], [])
        self.assertNotIn("_padding", card)
        counts = self.save["GameResults"]["highscores"][0][1]["TapCounts"]
        self.assertEqual([k for k in counts if k.startswith("Unused")], [])

    def test_unused_padding_bytes_are_preserved(self):
        save = json.loads(to_json(self.save))
        card = save["CardInventory"]["allCards"]["buffer"][0]
        card["_padding"] = {"10": "aabb", "60": "01020304"}
        again = decode(encode(save))["CardInventory"]["allCards"]["buffer"][0]
        self.assertEqual(again["_padding"], {"10": "aabb", "60": "01020304"})

    def test_trailing_bytes_rejected(self):
        with self.assertRaises(MemoryPackError):
            decode(self.data + b"\x00")

    def test_null_class_field(self):
        save = json.loads(to_json(self.save))
        save["CardInventory"] = None
        again = decode(encode(save))
        self.assertIsNone(again["CardInventory"])

    def test_null_struct_field_rejected(self):
        save = json.loads(to_json(self.save))
        save["GeneralSaveState"] = None
        with self.assertRaises(MemoryPackError):
            encode(save)


class IotaPackingTests(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(
            decode_base_iota_id_potency(8635),
            {
                "BaseIotaId": 2,
                "Potency": 110,
                "TraitCountRaw": 3,
                "TraitCount": 0,
                "Reserved": 0,
            },
        )
        self.assertEqual(
            decode_base_iota_id_potency(33211),
            {
                "BaseIotaId": 8,
                "Potency": 110,
                "TraitCountRaw": 3,
                "TraitCount": 0,
                "Reserved": 0,
            },
        )

    def test_roundtrip(self):
        for base in (1, 2, 8, 40):
            for potency in (0, 110, 999, 1023):
                for trait_count in range(4):
                    packed = encode_base_iota_id_potency(base, potency, trait_count)
                    decoded = decode_base_iota_id_potency(packed)
                    self.assertEqual(decoded["BaseIotaId"], base)
                    self.assertEqual(decoded["Potency"], potency)
                    self.assertEqual(decoded["TraitCount"], trait_count)

    def test_against_iota_table(self):
        if not os.path.exists(IOTAS):
            self.skipTest("data/Iotas.json not present")
        with open(IOTAS, "r", encoding="utf-8") as fh:
            table = {row["IotaId"]: row["Name"] for row in json.load(fh)}
        # red r-1-2 is base 2, green g-1-2 is base 8
        self.assertEqual(table[2], "r-1-2")
        self.assertEqual(table[8], "g-1-2")
        self.assertEqual(
            table[decode_base_iota_id_potency(8635)["BaseIotaId"]], "r-1-2"
        )
        self.assertEqual(
            table[decode_base_iota_id_potency(33211)["BaseIotaId"]], "g-1-2"
        )

    def test_save_instances_match_iota_table(self):
        if not (os.path.exists(SAVE) and os.path.exists(IOTAS)):
            self.skipTest("save or Iotas.json not present")
        with open(SAVE, "rb") as fh:
            save = decode(fh.read())
        with open(IOTAS, "r", encoding="utf-8") as fh:
            table = {row["IotaId"]: row["Name"] for row in json.load(fh)}
        holder = save["IotaInventory"]["allIota"]
        for item in holder["buffer"][: holder["length"]]:
            self.assertNotIn("BaseIotaIdPotency", item)
            self.assertIn(item["BaseIotaId"], table)
            nz = sum(1 for k in ("TraitId1", "TraitId2", "TraitId3") if item[k])
            self.assertEqual(item["TraitCount"], nz)
            self.assertNotIn("Reserved", item)

    def test_flat_fields_are_writable(self):
        if not os.path.exists(SAVE):
            self.skipTest("save not present")
        with open(SAVE, "rb") as fh:
            save = decode(fh.read())
        item = save["IotaInventory"]["allIota"]["buffer"][0]
        item["Potency"] = 111
        item["TraitCount"] = 1
        again = decode(encode(save))["IotaInventory"]["allIota"]["buffer"][0]
        self.assertEqual(again["Potency"], 111)
        self.assertEqual(again["TraitCount"], 1)
        self.assertIn("BaseIotaId", again)

    def test_packed_key_is_not_accepted(self):
        if not os.path.exists(SAVE):
            self.skipTest("save not present")
        with open(SAVE, "rb") as fh:
            save = decode(fh.read())
        item = save["IotaInventory"]["allIota"]["buffer"][0]
        for key in ("BaseIotaId", "Potency", "TraitCount"):
            del item[key]
        item["BaseIotaIdPotency"] = 8635
        with self.assertRaises(MemoryPackError):
            encode(save)


if __name__ == "__main__":
    unittest.main()
