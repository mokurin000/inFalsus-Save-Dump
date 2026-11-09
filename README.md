# In Falsus 存档编解码

纯 Python、无第三方依赖的存档解析/回写工具。`savestate_V3.sav` 已经过完整验证：

* 解码后重新编码，**277750 字节逐字节完全一致**；
* 解码 → JSON → 再编码，同样逐字节一致；
* 单元测试 `python -m unittest discover -s tests -v` 全部通过。

```
savecodec/
  mp.py       MemoryPack 底层读写（对象头、集合头、字符串、原始值）
  model.py    类型描述符（对象/结构体/数组/字典/UnorderedList…）
  schema.py   SingleFileSaveDataV2 及其全部嵌套类型的字段顺序和类型
  codec.py    decode / encode / to_json / from_json
  cli.py      命令行
tests/        单元测试
savestate_V3.json   示例输出（约 2.9 MB，缩进 2）
```

## 快速开始

```bash
# 存档 -> JSON
python -m savecodec to-json savestate_V3.sav savestate_V3.json

# JSON -> 存档
python -m savecodec from-json savestate_V3.json new.sav

# 检查二进制和 JSON 往返是否逐字节一致
python -m savecodec verify savestate_V3.sav

# 打印摘要
python -m savecodec info savestate_V3.sav
```

作为库使用：

```python
import json
from savecodec import decode, encode, to_json, from_json

data = open("savestate_V3.sav", "rb").read()
save = decode(data)                 # dict / list / int / float / str / bool / None
assert encode(save) == data

text = to_json(save)                # JSON 文本
assert encode(from_json(text)) == data

# 改一个值再写回
save["GeneralSaveState"]["AssistMode"] = True
open("edited.sav", "wb").write(encode(save))
```

## 验证过的 MemoryPack 线格式

这个游戏的 MemoryPack 版本与常见教程里的格式有几处不同，以下全部由
`GameAssembly.dll` 中的 `Serialize`/`Deserialize`（IL2CPP）确认，并由真实存档验证。

| 项目 | 编码 |
| --- | --- |
| 对象头（class / 非 blittable struct） | 1 字节成员数；`0xFF` = null；`0` = 0 个成员的非 null 对象 |
| 集合头（数组 / List / HashSet / Dictionary） | 小端 `int32` 元素数；`-1` = null |
| 字符串 | `int32 ~utf8字节数`（负数）+ `int32 UTF-16码元数` + UTF-8 字节；null 为 `-1`，空串为 `0`（都只占 4 字节） |
| 非托管（blittable）结构体 | 原始内存 `sizeof(T)` 字节，无头、无对齐填充追加 |
| 非托管结构体数组 | `int32` 个数 + 连续原始内存 |
| 非托管结构体字段 | 按内存布局原样写出；结构体内 padding 也属于线格式 |
| `Dictionary<K,V>` | `int32` 个数 + 按枚举顺序的 `(key, value)` 对，无额外头 |
| `HashSet<T>` / `List<T>` / `T[]` | `int32` 个数 + 每个元素 |
| `UnorderedListVal<T>` / `UnorderedListRef<T>` | 对象头 `2` + `T[] buffer` + `int32 length` |

### 字符串细节

```text
"cyaegha":  f8 ff ff ff | 07 00 00 00 | 63 79 61 65 67 68 61
            ~7 = -8        UTF-16 len=7  UTF-8 bytes
"":         00 00 00 00
null:       ff ff ff ff
```

非 BMP 字符（如 emoji）的 UTF-16 码元数是 2，而 UTF-8 字节数是 4，
所以第二个 `int32` 不能用 Python 的 `len(str)`，本实现用 `utf-16-le` 计算。

## 类型结构（成员顺序 = 序列化顺序）

根对象 `SingleFileSaveDataV2`，头字节 `9`：

| # | 字段 | 类型 |
| --- | --- | --- |
| 1 | `CardInventory` | CardInventory |
| 2 | `IotaInventory` | IotaInventory |
| 3 | `GameResults` | GameResultsV4 |
| 4 | `EncounterResults` | EncounterResults |
| 5 | `StoryToState` | StoryStateV5 |
| 6 | `GeneralSaveState` | GeneralSaveStateV5（struct，头 17） |
| 7 | `RecipeSaveState` | RecipeSaveStateV2 |
| 8 | `LootDropState` | LootDropState |
| 9 | `GrantsSaveState` | GrantsSaveState |

`CardInventory`（头 3）：`allCards` / `EncounterIdToSavedDeck` / `LastUsedDeckIndex`

`IotaInventory`（头 2）：`allIota` / `obsolete_ExistsBaseIotaIdPotency`
（`instanceExistsBaseIotaIdPotency`、`dirty` 不参与序列化）

`GameResultsV4`（头 4）：`highscores` / `history` / `songInfoMapping` / `updateId`

`EncounterResults`（头 2）：`results` / `updateId`

`StoryStateV5`（头 2）：`storyToState` / `updateId`

`RecipeSaveStateV2`（头 2）：`saveData` / `updateId`

`LootDropState`（头 2）：`dropStates` / `updateId`

`GrantsSaveState`（头 2）：`grants` / `updateId`

`GeneralSaveStateV5`（头 17，按此顺序）：

1. `SelectedCharacter`（u8 枚举）
2. `PackIdToSelectedSongId`（`Dictionary<u16,u16>`）
3. `LastSelectedPackId`（u16）
4. `LastSelectedDifficulty`（u8 枚举）
5. `LastSelectedSongSelectSortType`（i32 枚举）
6. `LastSecondarySortType`（i32 枚举）
7. `LastSelectedEncounterId`（i32）
8. `LastSelectedRecipeFilterParameters`（20 字节结构体）
9. `LastSelectedIotaFilterParameters`（8 字节）
10. `LastSelectedCardFilterParameters`（12 字节）
11. `LastSelectedRecipeId`（i32）
12. `TutorialFlags`（u64）
13. `EnabledAnyStoryFastForwardSkipping`（bool）
14. `StoryChoiceToResult`（`Dictionary<string,string>`）
15. `SeenSongVideoIds`（`HashSet<string>`）
16. `LastSelectedScenarioSongDifficulty`（u8 枚举）
17. `AssistMode`（bool）

`RecipeSaveDataV2`（头 17，按此顺序）：`RecipeIdStr`、`RevealedHexes`、
`RevealedSafeHexes`、`DefaultRevealedSafeHexCount`、`RemainingSafeHiddenHexes`、
`BonusAreasSeen`、`BonusAreasRevealed`、`RevealedBonusAreaBasePower`、
`RevealedBonusAreaBaseFortitude`、`RevealedRangeStartAmount`、
`RevealedRangeEndAmount`、`RevealedTraits`、`challengeCompleteFlags`、
`intuitionProgress`、`currentRecipeRandomSeed`、`hasEverCrafted`、
`IslandAreasRevealed`。

`GameResultsSongInfoMapping`（头 3）：`Mappings` / `HistoryIndexStart` / `HistoryIndexLength`

`SongInfoMapping`（头 2）：`BaseName` / `SongId`
`GameResultKey`（头 3）：`BaseName` / `SongId` / `Difficulty`

### 非托管结构体（原始字节，大小固定）

| 类型 | 大小 | 字段（偏移） |
| --- | ---: | --- |
| `CardInstance` | 64 | CardId@0, CardBaseId@4, TierIndex@8, IsSR@9, padding@10..11, CardColorType@12, BasePower@16, BaseFortitude@24, BaseRangeOffsetStart@32, BaseRangeOffsetEnd@36, TraitSlotType1..3@40/42/44, TraitId1..3@46/48/50, SecondsSinceEpochUtc@52, padding@60..63 |
| `SavedDeck` | 24 | CardIds[5]@0, Assigned@20, padding@21..23 |
| `BattleScore` | 56 | 6×double@0..47, NumberOfNotesJudged@48, TotalNoteCount@52 |
| `EncounterResult` | 72 | EncounterId@0, BattleScore@8, Success@64, SuccessType@68 |
| `IotaInstance` | 16 | BaseIotaIdPotency@0, TraitId1..3@4/6/8, UserData@10, Count@12, padding@14..15 |
| `GameResultV4` | 96 | SongId@0, Difficulty@2, Lamp@3, CalculatedResultClear@4, MaxCombo@6, CalculatedPaceValue@8, Tap/Hold/Sky/Flick Counts@10/26/42/58, PlayerScore@80, SecondsSinceEpochUtc@88 |
| `StoryEntryStateV5` | 16 | StoryIdentifier@0, MaxLineCountRead@4, IsRead@8, HasPlayedSongChallenge@9, HasAllowedFastForwardSkipping@10, LastQuitLineCountRead@12 |
| `JudgementTypeCount` | 16 | None/Miss/NearEarly/NearLate/PerfectEarly/PerfectLate/Shiny@0..13, padding@14..15 |
| `Hex` | 8 | Q/R/S（3×i16）, padding@6..7 |
| `IotaDropTableState` | 8 | 一个 private ulong（JSON 中名为 `Value`） |
| `RecipeFilterParameters` | 20 | 4×i32 + bool（含 3 字节 padding） |
| `IotaFilterParameters` | 8 | 2×i32 |
| `CardFilterParameters` | 12 | 3×i32 |

## JSON 约定

* `UnorderedListVal` / `UnorderedListRef` 变成
  `{"buffer": [...], "length": N}`。`buffer` 是**容量**（可能大于 `length`），
  游戏会把整个容量写进存档，未使用槽位里也可能有旧数据，因此本工具完整保留。
* string 键的字典（如 `StoryChoiceToResult`）输出为 JSON 对象（保持插入顺序）；
  其他字典（如 `highscores`、`storyToState`）输出为 `[[key, value], ...]` 数组，
  因为 JSON 对象的 key 只能是字符串。
* 枚举输出为名字（只在该值正好等于某个枚举成员时），否则输出整数；
  回写时名字和整数都接受。
* `_padding` 只在结构体 padding 字节非零时出现，形如
  `{"5": "ff", "74": "000000000000"}`（键是结构体内的字节偏移，值是该段
  十六进制字节）。普通修改不要动它就能保持字节级一致。
* 源码里的 `Unused*` 字段（`CardInstance.UnusedByte*` / `Unused1`、
  `IotaInstance.Unused`、`JudgementTypeCount.Unused*`、`Hex.Unused`）在存档中
  全为 0，按 padding 处理，不再作为 JSON 字段输出；若某个存档里它们非 0，
  会自动出现在 `_padding` 中，仍可原样回写。
* 64 位整数在 Python JSON 中是精确整数，不会丢精度。
* `null` 和空数组/空字符串是不同状态：`null` 对应 MemoryPack 的 null 头，
  空集合对应长度 0。

## BaseIotaIdPotency 不是 ID，而是位域

`IotaInstance.BaseIotaIdPotency` 把 base iota、potency 和 trait 数量打包进一个 32 位整数：

| bits | 含义 |
| --- | --- |
| 0..1 | `TraitCountRaw` = `3 - TraitCount` |
| 2..11 | `Potency`（10 位，0..1023） |
| 12..17 | `BaseIotaId`（6 位，0..63；实际使用 1..40） |
| 18..31 | 保留，当前存档中恒为 0 |

对应反编译得到的 getter / `GetDefaultTuple`：

```text
get_TraitCountRaw() = value & 3
get_Potency()       = (value >> 2)  & 0x3FF
get_BaseIotaId()    = (value >> 12) & 0x3F
pack(base, potency, traitCount) = (base << 12) | (potency << 2) | (~traitCount & 3)
```

用 `data/iota.json`（`IotaId -> Name`，名称格式为 `颜色-阶-形状`）验证：

```text
8635  = 0x21BB -> BaseIotaId=2  (r-1-2，红色)   Potency=110  TraitCount=0
33211 = 0x81BB -> BaseIotaId=8  (g-1-2，绿色)   Potency=110  TraitCount=0
```

即：两个粒子都是 **potency 110、tier 1、shape 2、无特性**，区别只在颜色和 base ID。
存档里的 390 个 iota 实例全部能按此公式解出 1..40 的合法 BaseIotaId，
且解出的 `TraitCount` 与 `TraitId1..3` 的非零个数完全一致。

JSON 导出里该字段已经展开，不再是 `BaseIotaIdPotency: 8635`：

```json
{
  "BaseIotaId": 2,
  "Potency": 110,
  "TraitCount": 0,
  "TraitId1": 0,
  "TraitId2": 0,
  "TraitId3": 0,
  "UserData": 0,
  "Count": 14
}
```

回写时会按上表重新打包。

注意：`BaseIotaIdPotency` 不是 `IotaDetails.Id`，所以在 MonoBehaviour 导出里直接搜
8635/33211 是搜不到的；解码后按 `BaseIotaId`（2、8）去 `data/iota.json` 或
`RecipeSpecificationDetails.sparseIotas`（`IotaDetails[]`）里查。其中用 Q/R/S 表示了粒子形状。

## 结论是怎么来的

Schema 不是从字段布局猜的，而是逐个反编译生成的序列化函数得到的：

| 函数 | RVA |
| --- | --- |
| `SingleFileSaveDataV2.Serialize` | `0x4BBF90` |
| `CardInventory.Serialize` | `0x484A70` |
| `IotaInventory.Serialize` | `0x4A8000` |
| `GameResultsV4.Serialize` | `0x4A1D70` |
| `EncounterResults.Serialize` | `0x48B170` |
| `StoryStateV5.Serialize` | `0x4C3E40` |
| `GeneralSaveStateV5.Serialize` | `0x4A4A10` |
| `RecipeSaveStateV2.Serialize` | `0x4B8C90` |
| `LootDropState.Serialize` | `0x4A9A70` |
| `GrantsSaveState.Serialize` | `0x4A5690` |

关键底层函数：`WriteNullObjectHeader`（`0x180480820`，写 `0xFF`）、
`WriteObjectHeader`（`0x181708CE0`）、`WriteCollectionHeader`（`0x180480730`，4 字节）、
`WriteString`（名称 `sub_180480A00`）。

`GeneralSaveStateV5` 的 68 字节块由 `sub_18000D3F0` 逐字段写出（无 padding）；
`GrantsSaveState` 的 `WriteUnmanagedWithObjectHeader<SingleTimeGrant,long>` 写头 2 + 16 字节。

## 限制

* 只处理 MemoryPack 负载本身；当前存档没有压缩/加密包装。如果其他平台/版本
  在文件外又套了 gzip、Brotli 或自定义头，需要先剥掉。
* 对象头成员数是严格的。若游戏升级后改变某类型的成员数，会抛出
  `header is N but schema expects M`，不会静默错位；此时需要按新版本补 schema。
* 不支持多态/union 类型（本存档图中没有）。
* 旧的 `SingleFileSaveData`（V1）没有包含；当前目标是 `SingleFileSaveDataV2`。
