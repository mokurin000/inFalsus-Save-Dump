"""把 TraitId 解析成对应的 Frame / Icon 素材名。

素材命名约定（data/trait/ 下）：
  Frame-large-<Frame>.webp
  Icon-<Effect>-<active|passive>.webp

规则来自 GameAssembly.dll 反编译（详见 docs/trait-icons.md）：

  ifapp.Game.UI.Common.TraitIcon._qsA(in TraitSpecification spec, bool, bool mini, bool)
    RVA 0x5076C0

  Frame  <=  (EffectCount == 0)                       -> EmptyLargeFrame
             Effect0.TAC == 8  && Effect1.TAC == 3    -> Graceless
             Effect0.TAC == 10 && Effect1.TAC == 1    -> Winged
             其他                                      -> ActivationConditionToLargeFrame[Effect0.TAC]

  Icon   <=  (Effect0.TraitEffect < 0x1FA0 ? TraitEffectPassiveToIcon
                                           : TraitEffectActiveToIcon)[spec.Icon]

也就是说：Frame 由「首个效果的触发条件」决定，Icon 由「spec.Icon 这个 0..16 的
枚举」决定，而 -active / -passive 由「首个效果是不是瞬时效果（伤害 8096 / 治疗
8097）」决定。

spec.Icon 只存在于 GameData.asset（GameData.traits[]，每个 32 字节），字符串 id
里没有；所以本脚本有两种模式：

  1. --game-data <GameData.json>：读真实表，结果精确。
  2. 默认：从 TraitIdStr / 英文名反推（字符串里带着同样的信息），
     输出里 Confidence 字段标明来源。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIT_JSON = ROOT / "data" / "trait.json"

# TraitActivationCondition 枚举值 -> Frame 素材名。
# 下标就是枚举值：ActivationConditionToLargeFrame[Effect0.TraitActivationCondition]。
FRAME_BY_CONDITION = {
    0: "Border",  # None
    1: "Closing",  # WhenDeactivates
    2: "EchoingClosing",  # WhenCardInRangeDeactivates
    3: "LingeringClosing",  # WhenExitingThisCardRange
    4: "Outer",  # WhileSelfNotActive
    5: "RangedOuter",  # WhileNotInThisCardRange
    6: "Inner",  # WhileSelfActive
    7: "RangedInner",  # WhileInThisCardRange
    8: "OnsetOpening",  # WhenEnteringThisCardRange
    9: "RecurringOpening",  # WhenCardInRangeActivates
    10: "Opening",  # WhenActivates
}

# TraitIdStr 里的触发条件词 -> TraitActivationCondition。
# 顺序重要：先匹配更长的词（every-activate 含 activate，inactive 含 active...）。
CONDITION_BY_TOKEN = [
    ("every-activate", 9),
    ("every-deactivate", 2),
    ("deactivate", 1),
    ("activate", 10),
    ("enter", 8),
    ("exit", 3),
    ("inactive", 4),
    ("outrange", 5),
    ("active", 6),
    ("range", 7),
    ("border", 0),
]

# TraitIdStr 里的效果族 -> Icon 素材名（None = 这个族没有出图）。
ICON_BY_FAMILY = {
    "damage-efficacy": "Surge",
    "heal-amount": "Recover",
    "percent-all": "Amplification",
    "percent-fortitude": "Rigor",
    "percent-power": "Concentration",
    "denominator-all": "Distress",
    "denominator-fortitude": "Vulnerable",
    "denominator-power": "Weaken",
}

# 效果族 -> 首个效果是不是瞬时效果（TraitEffect >= 0x1FA0，即 8096 伤害 / 8097 治疗）。
# 只有这两族走 TraitEffectActiveToIcon，其余走 TraitEffectPassiveToIcon。
TRIGGER_FAMILIES = {"damage-efficacy", "heal-amount"}

# 英文名里的 Frame 前缀（unique-* 的 id 里没有条件词，只能看名字）。
NAME_FRAME_PREFIX = [
    ("Ranged Inner", 7),
    ("Ranged Outer", 5),
    ("Ranged Border", 0),  # 名字这么写，但素材里没有 RangedBorder，按 Border 处理
    ("Triple Closing", 1),
    ("Ranged", 7),  # 兜底："Ranged Xxx" 就是 RangedInner（Chromatic Isolation）
    ("Opening", 10),
    ("Closing", 1),
    ("Onset", 8),
    ("Recurring", 9),
    ("Echoing", 2),
    ("Lingering", 3),
    ("Inner", 6),
    ("Outer", 4),
    ("Border", 0),
]

# 英文名里的 Icon 词 -> 素材名（None = 没有出图）。
ICON_BY_WORD = {
    "Full Recovery": "FullRecover",
    "Recovery": "Recover",
    "Surge": "Surge",
    "Distress": "Distress",
    "Vulnerability": "Vulnerable",
    "Digression": "Weaken",
    "Amplification": "Amplification",
    "Rigor": "Rigor",
    "Concentration": "Concentration",
    "Aegis": "Aegis",
    "Turmoil": "Turmoil",
    "Burst": "Burst",
    "Isolation": "ChromaticIsolation",
    "Critical Focus": "CriticalFocus",
    "Impudence": "Impudence",
    "Weaken": "Weaken",
}

# 只有一张图、没有 -active / -passive 两个状态的图标。
# Icon-ChromaticIsolation.webp 只给 Ranged Chromatic Isolation: Red 用。
STATE_LESS_EFFECTS = {"ChromaticIsolation"}

# 逐个 trait 确认过的特例（其余走 id 词 / 英文名的通用规则）。
OVERRIDES: dict[int, dict] = {
    # 66 = "Ranged Chromatic Isolation: Red"：Frame 是 RangedInner，没有 tier
    66: {"ActivationCondition": 7, "Tier": 0, "Confidence": "user-confirmed"},
}


def frame_file(name: str | None) -> str | None:
    return None if name is None else f"Frame-large-{name}.webp"


def icon_file(effect: str | None, active: bool | None = None) -> str | None:
    """active=None 表示两态未知，返回 `Icon-X-*.webp` 让调用方自己挑。"""
    if effect is None:
        return None
    if effect in STATE_LESS_EFFECTS:
        return f"Icon-{effect}.webp"
    if active is None:
        return f"Icon-{effect}-*.webp"
    return f"Icon-{effect}-{'active' if active else 'passive'}.webp"


def condition_from_id(id_str: str) -> tuple[int, str] | None:
    for token, cond in CONDITION_BY_TOKEN:
        if f"-{token}-" in f"-{id_str}-" or id_str.endswith(f"-{token}"):
            return cond, token
    return None


def family_from_id(id_str: str) -> str | None:
    stripped = id_str.removeprefix("demo-")
    for family in sorted(ICON_BY_FAMILY, key=len, reverse=True):
        if stripped.startswith(family):
            return family
    return None


def split_name(name: str) -> tuple[int | None, str | None]:
    """'Ranged Inner Rigor III' -> (7, 'Rigor')；只用于 unique-* 拆名字。"""
    base = re.sub(r"\s*:\s*.*$", "", name)  # 去掉 ": Red" 这类后缀
    base = re.sub(r"\s+(I{1,3}|IV|V|\d+)$", "", base).strip()
    frame = None
    rest = base
    for prefix, cond in NAME_FRAME_PREFIX:
        if base.startswith(prefix + " "):
            frame, rest = cond, base[len(prefix) + 1 :]
            break
    effect = None
    for word in sorted(ICON_BY_WORD, key=len, reverse=True):
        if rest.endswith(word):
            effect = ICON_BY_WORD[word]
            break
    return frame, effect


def tier_from_id(id_str: str) -> int | None:
    m = re.search(r"-t(\d)$", id_str)
    return int(m.group(1)) if m else None


def derive(trait: dict) -> dict:
    tid = trait["TraitId"]
    id_str = trait["TraitIdStr"]
    name_en = (trait.get("Name") or {}).get("English", "")

    row = {
        "TraitId": tid,
        "Name": name_en,
        "ActivationCondition": None,
        "Frame": None,
        "Effect": None,
        "State": None,  # active / passive / None(未知)
        "Icon": None,
        "Tier": tier_from_id(id_str),
        "Confidence": "id-token",
    }

    if id_str == "unique-trait":  # EffectCount == 0，游戏显示空框 + 隐藏图标
        row.update(Confidence="empty")
        return row

    family = family_from_id(id_str)
    cond = condition_from_id(id_str)

    if family is None or cond is None:  # unique-*：id 里没有条件词/效果词，只能看英文名
        frame, effect = split_name(name_en)
        row.update(
            ActivationCondition=frame,
            Effect=effect,
            Confidence="name-guess",
        )
        if frame is not None:
            row["Frame"] = frame_file(FRAME_BY_CONDITION.get(frame))
        # active/passive 取决于表里的 Effect0.TraitEffect，名字推不出来；
        # 无两态的图标（ChromaticIsolation）这里就能给出确切文件名
        row["Icon"] = icon_file(effect)
        row.update(OVERRIDES.get(tid, {}))
        return row

    cond_value, _ = cond
    active = family in TRIGGER_FAMILIES
    effect = ICON_BY_FAMILY[family]
    row.update(
        ActivationCondition=cond_value,
        Frame=frame_file(FRAME_BY_CONDITION[cond_value]),
        Effect=effect,
        State="active" if active else "passive",
        Icon=icon_file(effect, active),
    )
    if effect is None:
        row["Confidence"] = "id-token-no-art"
    row.update(OVERRIDES.get(tid, {}))
    return row


def _int(value) -> int | None:
    """吃 int / {"Value": n} / "Name"。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return _int(value.get("Value", value.get("value")))
    if isinstance(value, str):
        value = value.strip()
        return (
            int(value) if re.fullmatch(r"-?\d+", value) else KNOWN_ENUM_NAMES.get(value)
        )
    return int(value)


# 只用于让 --game-data 能吃「导出时保留了枚举名」的情况
KNOWN_ENUM_NAMES = {
    "None": 0,
    "WhenDeactivates": 1,
    "WhenCardInRangeDeactivates": 2,
    "WhenExitingThisCardRange": 3,
    "WhileSelfNotActive": 4,
    "WhileNotInThisCardRange": 5,
    "WhileSelfActive": 6,
    "WhileInThisCardRange": 7,
    "WhenEnteringThisCardRange": 8,
    "WhenCardInRangeActivates": 9,
    "WhenActivates": 10,
}


def load_game_data(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("traits") or data.get("Traits") or []
    return data


def resolve_from_game_data(
    spec: dict, names: dict[int, str]
) -> tuple[str | None, str | None]:
    """返回 (frame 素材名, icon 素材名)，完全照 _qsA 的逻辑。"""
    effect0 = spec.get("Effect0") or {}
    effect1 = spec.get("Effect1") or {}
    count = _int(spec.get("EffectCount")) or 0
    cond0 = _int(effect0.get("TraitActivationCondition")) or 0
    cond1 = _int(effect1.get("TraitActivationCondition")) or 0
    trait_effect = _int(effect0.get("TraitEffect")) or 0

    if count == 0:
        frame = "Empty"
    elif count == 2 and cond0 == 8 and cond1 == 3:
        frame = "Graceless"
    elif count == 2 and cond0 == 10 and cond1 == 1:
        frame = "Winged"
    else:
        frame = FRAME_BY_CONDITION.get(cond0)

    icon = None
    if count > 0:
        effect = names.get(_int(spec.get("Icon")) or 0)
        active = trait_effect >= 0x1FA0
        icon = icon_file(effect, active)
    return frame_file(frame), icon


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trait-json", type=Path, default=TRAIT_JSON)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "trait-icon.json")
    ap.add_argument(
        "--game-data",
        type=Path,
        help="GameData ScriptableObject 的 MonoBehaviour JSON dump；给了就按真表算",
    )
    args = ap.parse_args()

    traits = json.loads(args.trait_json.read_text(encoding="utf-8"))
    rows = [derive(t) for t in sorted(traits, key=lambda t: t["TraitId"])]

    if args.game_data:
        table = load_game_data(args.game_data)
        # spec.Icon(0..16) 的 名字 只能从资产里学：用字符串模式的结果按 Icon 值投票
        votes: dict[int, dict[str, int]] = {}
        for r in rows:
            spec = table[r["TraitId"]] if r["TraitId"] < len(table) else None
            if not spec or not r["Effect"]:
                continue
            icon_id = _int(spec.get("Icon")) or 0
            votes.setdefault(icon_id, {}).setdefault(r["Effect"], 0)
            votes[icon_id][r["Effect"]] += 1
        names = {k: max(v, key=v.get) for k, v in votes.items()}

        for r in rows:
            spec = table[r["TraitId"]] if r["TraitId"] < len(table) else None
            if not spec:
                r["Confidence"] = "missing-in-game-data"
                continue
            frame, icon = resolve_from_game_data(spec, names)
            r.update(
                Frame=frame,
                Icon=icon,
                State=None
                if icon is None
                else ("active" if "active" in icon else "passive"),
                ActivationCondition=_int(
                    (spec.get("Effect0") or {}).get("TraitActivationCondition")
                ),
                Tier=_int(spec.get("Tier")),
                Confidence="game-data",
            )
        print("spec.Icon -> 名字（从英文名投票得到，冲突说明某处不一致）:")
        for icon_id in sorted(votes):
            print(f"  {icon_id:>2} -> {names[icon_id]:<14} {votes[icon_id]}")

    payload = rows
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )

    for r in rows:
        print(
            f"{r['TraitId']:>3}  {r['Name'][:34]:<34} {r['Frame']!s:<34} "
            f"{r['Icon']!s:<32} {r['Confidence']}"
        )
    print(f"\n{len(rows)} traits -> {args.out}")


if __name__ == "__main__":
    main()
