# In Falsus 存档编解码

纯 Python、无第三方依赖的存档解析 / 回写工具：把游戏的 `SingleFileSaveDataV2` 存档
在 MemoryPack 二进制和 JSON 之间互转。

已用真实存档验证：解码后重新编码**逐字节完全一致**，
解码 → JSON → 再编码同样逐字节一致。

## 安装

需要 Python ≥ 3.10，无依赖。

```bash
pip install -e .        # 可选；装了之后有 savecodec 命令
```

不安装也能用，在仓库根目录直接 `python -m savecodec ...`。

## 命令行

| 命令 | 作用 |
| --- | --- |
| `to-json <save> <json>` | 存档 → JSON |
| `from-json <json> <save>` | JSON → 存档 |
| `verify <save>` | 检查「二进制」和「二进制 → JSON → 二进制」是否都逐字节一致 |
| `info <save>` | 打印一段摘要（卡牌数、iota 数、成绩条数、updateId…） |

```bash
# 存档 -> JSON
python -m savecodec to-json savestate_V3.sav savestate_V3.json

# JSON -> 存档
python -m savecodec from-json savestate_V3.json new.sav

# 往返自检
python -m savecodec verify savestate_V3.sav

# 摘要
python -m savecodec info savestate_V3.sav
```

`to-json` 的选项：`--indent N`（默认 4）、`--compact`（不缩进）。

## 作为库使用

```python
from savecodec import decode, encode, from_json, to_json

data = open("savestate_V3.sav", "rb").read()
save = decode(data)                 # dict / list / int / float / str / bool / None
assert encode(save) == data

text = to_json(save)                # JSON 文本
assert encode(from_json(text)) == data

# 改一个值再写回
save["GeneralSaveState"]["AssistMode"] = True
open("edited.sav", "wb").write(encode(save))
```

`savestate_V3.sav` / `savestate_V3.json` 是示例文件名，不在仓库里 —— 换成你自己的路径。

## 输出长什么样

* 顶层就是 9 个键：`CardInventory`、`IotaInventory`、`GameResults`、`EncounterResults`、
  `StoryToState`、`GeneralSaveState`、`RecipeSaveState`、`LootDropState`、`GrantsSaveState`。
* `UnorderedListVal` / `UnorderedListRef` 是 `{"buffer": [...], "length": N}`，
  `buffer` 是容量（可能大于 `length`，多出来的槽位游戏也会写进存档）。
* `string` 键的字典输出成 JSON 对象，其他字典输出成 `[[key, value], ...]`。
* 枚举输出成名字（值正好等于某个成员时），回写时名字和整数都收。
* `_padding` 只在结构体 padding 非零时出现；不要动它就能保持字节级一致。
* `null` 与空数组/空字符串是不同状态，不会互相折叠。

字段含义、完整约定和字节布局见 [docs/save-file.md](docs/save-file.md)。

## 项目结构

```
savecodec/
  mp.py       MemoryPack 底层读写（对象头、集合头、字符串、原始值）
  model.py    类型描述符（对象/结构体/数组/字典/UnorderedList…）
  schema.py   SingleFileSaveDataV2 及其全部嵌套类型的字段顺序和类型
  codec.py    decode / encode / to_json / from_json
  cli.py      命令行
  iota.py     BaseIotaIdPotency 位域的拆解/打包
tests/        单元测试
docs/
  save-file.md    存档格式与逆向手记
  trait-icons.md  trait 图标素材的选择规则
data/         游戏内导出的表（iota / recipe / trait）与贴图
tools/        一次性脚本（表导出、trait 图标推导）
```

## 测试

```bash
python -m unittest discover -s tests -v
```

## 限制

* 只认当前的 `SingleFileSaveDataV2`（旧的 V1 没做）。
* 对象头成员数严格校验：游戏改了字段就会报 `header is N but schema expects M`，
  不会静默错位。
* 不支持多态 / union 类型。
* 只处理 MemoryPack 负载本身；如果某个平台在文件外又套了压缩或加密，需要先剥掉。

更多边界情况见 [docs/save-file.md](docs/save-file.md) 的「限制 / 已知边界」一节。
