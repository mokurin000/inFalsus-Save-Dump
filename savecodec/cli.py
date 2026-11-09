"""Command line interface: ``python -m savecodec``."""

from __future__ import annotations

import argparse
import sys

from .codec import (
    decode,
    dumps,
    encode,
    from_json,
    load_json_file,
    save_json_file,
    to_json,
)
from .mp import MemoryPackError


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(data)


def summarize(save: dict) -> str:
    ci = save.get("CardInventory") or {}
    ii = save.get("IotaInventory") or {}
    gr = save.get("GameResults") or {}
    er = save.get("EncounterResults") or {}
    ss = save.get("StoryToState") or {}
    gs = save.get("GeneralSaveState") or {}
    rs = save.get("RecipeSaveState") or {}
    ld = save.get("LootDropState") or {}
    gg = save.get("GrantsSaveState") or {}

    cards = (ci.get("allCards") or {}).get("buffer") or []
    card_len = (ci.get("allCards") or {}).get("length")
    iotas = (ii.get("allIota") or {}).get("buffer") or []
    iota_len = (ii.get("allIota") or {}).get("length")
    history_len = (gr.get("history") or {}).get("length")
    highscores = gr.get("highscores") or {}
    results_len = (er.get("results") or {}).get("length")
    stories = ss.get("storyToState") or {}
    recipes = rs.get("saveData") or {}
    drops_len = (ld.get("dropStates") or {}).get("length")

    def n(x):
        if x is None:
            return 0
        return len(x) if not isinstance(x, int) else x

    last_deck = dumps(ci.get("LastUsedDeckIndex"), indent=None)
    selected_character = dumps(gs.get("SelectedCharacter"), indent=None)
    song_mapping_len = n((gr.get("songInfoMapping") or {}).get("length"))
    grants = gg.get("grants") or 0
    game_update = dumps(gr.get("updateId"), indent=None)
    encounter_update = dumps(er.get("updateId"), indent=None)
    story_update = dumps(ss.get("updateId"), indent=None)
    recipe_update = dumps(rs.get("updateId"), indent=None)
    loot_update = dumps(ld.get("updateId"), indent=None)

    lines = [
        "SingleFileSaveDataV2",
        (
            f"  CardInventory        : {n(cards)} card slot(s), "
            f"{n(card_len)} card(s), last deck {last_deck}"
        ),
        f"  IotaInventory        : {n(iotas)} iota slot(s), {n(iota_len)} iota(s)",
        (
            f"  GameResults          : {n(highscores)} highscore(s), "
            f"{n(history_len)} history entr(ies), "
            f"{song_mapping_len} song mapping(s)"
        ),
        f"  EncounterResults     : {n(results_len)} result(s)",
        f"  StoryState           : {n(stories)} story state(s)",
        (
            f"  GeneralSaveState     : character {selected_character}, "
            f"{n(gs.get('PackIdToSelectedSongId'))} pack song(s), "
            f"{n(gs.get('StoryChoiceToResult'))} choice(s)"
        ),
        f"  RecipeSaveState      : {n(recipes)} recipe(s)",
        f"  LootDropState        : {n(drops_len)} drop table(s)",
        (
            f"  GrantsSaveState      : grants=0x{grants:X} "
            f"updateId={dumps(gg.get('updateId'), indent=None)}"
        ),
        (
            f"  updateIds            : game={game_update} "
            f"encounter={encounter_update} story={story_update} "
            f"recipe={recipe_update} loot={loot_update}"
        ),
    ]
    # keep locals used above intentional
    return "\n".join(lines)


def cmd_to_json(args) -> int:
    data = _read_bytes(args.save)
    save = decode(data)
    indent = None if args.compact else args.indent
    save_json_file(args.json, save, indent=indent)
    print(f"wrote {args.json} ({len(data)} bytes of save -> JSON)")
    return 0


def cmd_from_json(args) -> int:
    save = load_json_file(args.json)
    data = encode(save)
    _write_bytes(args.save, data)
    print(f"wrote {args.save} ({len(data)} bytes)")
    return 0


def cmd_verify(args) -> int:
    data = _read_bytes(args.save)
    save = decode(data)
    again = encode(save)
    if again != data:
        i = next(
            (k for k in range(min(len(data), len(again))) if data[k] != again[k]),
            min(len(data), len(again)),
        )
        got = data[i] if i < len(data) else -1
        expected = again[i] if i < len(again) else -1
        print(
            f"binary round-trip FAILED at offset 0x{i:X} (0x{got:X} vs 0x{expected:X})",
            file=sys.stderr,
        )
        return 1
    text = to_json(save)
    save2 = from_json(text)
    again2 = encode(save2)
    if again2 != data:
        print("JSON round-trip FAILED", file=sys.stderr)
        return 1
    print(f"OK: {len(data)} bytes decode/encode byte-identically, JSON round-trip OK")
    return 0


def cmd_info(args) -> int:
    save = decode(_read_bytes(args.save))
    print(summarize(save))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="savecodec",
        description="Convert In Falsus SingleFileSaveDataV2 saves "
        "between MemoryPack binary and JSON.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("to-json", help="decode a .sav file into JSON")
    a.add_argument("save")
    a.add_argument("json")
    a.add_argument("--indent", type=int, default=4, help="JSON indent (default 4)")
    a.add_argument("--compact", action="store_true", help="no whitespace")
    a.set_defaults(func=cmd_to_json)

    b = sub.add_parser("from-json", help="encode JSON back into a .sav file")
    b.add_argument("json")
    b.add_argument("save")
    b.set_defaults(func=cmd_from_json)

    c = sub.add_parser("verify", help="check binary and JSON round-trips")
    c.add_argument("save")
    c.set_defaults(func=cmd_verify)

    d = sub.add_parser("info", help="print a short summary of a save")
    d.add_argument("save")
    d.set_defaults(func=cmd_info)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (MemoryPackError, OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
