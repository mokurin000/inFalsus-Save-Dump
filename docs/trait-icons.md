# Trait 图标素材是怎么选出来的

全部结论来自 `dump/GameAssembly.dll.i64` 的反编译，核心函数只有一个：

| 函数 | RVA | 说明 |
| --- | --- | --- |
| `ifapp.Game.UI.Common.TraitIcon._qsA(in TraitSpecification, bool, bool mini, bool)` | `0x5076C0` | 唯一一处把 trait 数据变成 frame / icon 素材的地方 |
| `ifapp.Game.UI.Common.TraitIcon._QsA()` | `0x5074A0` | 清空：frame = Empty，icon = `TraitEffectActiveToIcon[0]` |
| `ifapp.Game.Data.GameData._rmA(TraitId)` | `0x48C070` | `traits[TraitId.Value]`，数组下标 **就是** TraitId |
| `ifapp.Game.Data.TraitSpecificationEffect.DoesTargetSelf()` | `0x4C4FC0` | `TraitEffect < 0x80`（本次没用上） |

## 1. 数据：GameData.asset 里的 32 字节结构

图标选择完全由 `GameData.traits[]` 里的字段决定，跟 `TraitIdStr`、名字都无关
（那两者只是恰好同义）。

```csharp
// ifapp.Game.Data.TraitSpecification, 32 字节，无对齐填充
public struct TraitSpecification {
    public TraitSpecificationEffect Effect0;  // 0x00
    public TraitSpecificationEffect Effect1;  // 0x0C
    public TraitId  Id;                       // 0x18  (short Value)
    public byte     EffectCount;              // 0x1A
    public _uH      Icon;                     // 0x1B  ← 唯一决定图标图案的字段
    public byte     Tier;                     // 0x1C  ← 1..3
    public byte[3]  Unused;                   // 0x1D
}

// 12 字节
public struct TraitSpecificationEffect {
    public long  Parameter0;                          // 0x00
    public ushort TraitEffect;                        // 0x08  ← 决定 active/passive
    public TraitActivationCondition TraitActivationCondition; // 0x0A ← 决定 Frame
    public byte  Unused0;                             // 0x0B
}

public enum _uH { _Ifb=0, _jfb=1, ... _Qfb=16 }        // 0..16 共 17 个槽位
public enum TraitActivationCondition {                 // 0..10
    None=0, WhenDeactivates=1, WhenCardInRangeDeactivates=2,
    WhenExitingThisCardRange=3, WhileSelfNotActive=4, WhileNotInThisCardRange=5,
    WhileSelfActive=6, WhileInThisCardRange=7, WhenEnteringThisCardRange=8,
    WhenCardInRangeActivates=9, WhenActivates=10,
}
```

素材表 `TraitIconAssets`（ScriptableObject）才是「枚举值 → 图片」的桥：

```csharp
public sealed class TraitIconAssets : ScriptableObject {
    public Material EmptySmallFrame;                        // 0x18
    public Material EmptyLargeFrame;                        // 0x20
    public Material[] ActivationConditionToSmallFrame;      // 0x28  下标 = TraitActivationCondition
    public Material[] ActivationConditionToLargeFrame;      // 0x30  下标 = TraitActivationCondition
    public Material[] TraitEffectActiveToIcon;              // 0x38  下标 = spec.Icon
    public Material[] TraitEffectPassiveToIcon;             // 0x40  下标 = spec.Icon
    public Material[] TraitTierToSmallIcon;                 // 0x48  下标 = Tier-1
    public Material[] TraitTierToLargeIcon;                 // 0x50  下标 = Tier-1
    public float[]    ActivationConditionToTierLargeIconYOffset; // 0x58 下标 = Conditioning
    public Material GracelessSmallFrame;  public Material GracelessLargeFrame;  // 0x60 / 0x68
    public Material WingedSmallFrame;     public Material WingedLargeFrame;     // 0x70 / 0x78
    // 0x80 起是同名的 *Mini 一套（列表/背包用的小尺寸）
}
```

所以：

- `Frame-large-<X>.webp` 里的 `<X>` = `ActivationConditionToLargeFrame[Effect0.TraitActivationCondition]`
- `Icon-<E>-<state>.webp` 里的 `<E>` = `(state==active ? TraitEffectActiveToIcon : TraitEffectPassiveToIcon)[spec.Icon]`

## 2. Frame：由「首个效果的触发条件」决定

反编译（`0x5076C0`，寄存器 `rdi` = `TraitSpecification*`、`rbx` = TraitIcon*）：

```text
142  movzx  esi, byte ptr [rdi+1Ah]      ; esi = EffectCount
143  cmp    sil, 2
144  jnz    loc_180507AC1                ; 不是 2 个效果 -> 直接按 Effect0 取
145  cmp    byte ptr [rdi+0Ah], 8        ; Effect0.TAC == WhenEnteringThisCardRange ?
147  cmp    byte ptr [rdi+16h], 3        ; Effect1.TAC == WhenExitingThisCardRange ?
                                                                  -> Graceless 框
159  cmp    byte ptr [rdi+0Ah], 0Ah      ; Effect0.TAC == WhenActivates ?
161  cmp    byte ptr [rdi+16h], 1        ; Effect1.TAC == WhenDeactivates ?
                                                                  -> Winged 框
173  movzx  eax, byte ptr [rdi+16h]      ; Effect0.TAC != Effect1.TAC -> Debug.LogWarning
...
227  movzx  r12d, byte ptr [rdi+0Ah]    ; r12 = Effect0.TAC
232  cmp    eax, [r13+18h]               ; 越界检查
238  mov    rdx, [r13+rax*8+20h]         ; rdx = ActivationConditionTo*Frame[TAC]
```

`r13` 在函数头由 `style` 选择（`1805078C3: cmovnz r13, [rsp+value]`）：

```text
style != 2 -> ActivationConditionToLargeFrame   (0x30)
style == 2 -> ActivationConditionToSmallFrame   (0x28)
```

伪代码：

```csharp
Material frame;
if (spec.EffectCount == 0)
    frame = mini ? a.EmptyLargeFrameMini : a.EmptyLargeFrame;          // 没有效果 -> 空框
else if (spec.EffectCount == 2 && spec.Effect0.TAC == WhenEnteringThisCardRange
                              && spec.Effect1.TAC == WhenExitingThisCardRange)
    frame = 小/大 ? GracelessSmall/LargeFrame;                          // Graceless
else if (spec.EffectCount == 2 && spec.Effect0.TAC == WhenActivates
                              && spec.Effect1.TAC == WhenDeactivates)
    frame = 小/大 ? WingedSmall/LargeFrame;                             // Winged
else
    frame = ActivationConditionTo{Small|Large}Frame[(int)spec.Effect0.TAC];
```

即 **Frame 只取决于 `Effect0.TraitActivationCondition`（0..10），下标就是枚举值**。
`Effect1` 只在两个「互补条件」特例里参与判断；互补但不是上面两对时，游戏还会打一条警告：

> `TraitSpecification has multiple effects but they are not complementary: `
> `EffectCount={0}, Effect0.Condition={1}, Effect1.Condition={2}`

数组槽位与素材名的对应（11 个槽位 = 11 个非特例 Frame）：

| `TraitActivationCondition` | 值 | 素材 | `TraitIdStr` 里的词 |
| --- | ---: | --- | --- |
| `None` | 0 | `Frame-large-Border` | `border`（以及无条件的 unique） |
| `WhenDeactivates` | 1 | `Frame-large-Closing` | `deactivate` |
| `WhenCardInRangeDeactivates` | 2 | `Frame-large-EchoingClosing` | `every-deactivate` |
| `WhenExitingThisCardRange` | 3 | `Frame-large-LingeringClosing` | `exit` |
| `WhileSelfNotActive` | 4 | `Frame-large-Outer` | `inactive` |
| `WhileNotInThisCardRange` | 5 | `Frame-large-RangedOuter` | `outrange` |
| `WhileSelfActive` | 6 | `Frame-large-Inner` | `active` |
| `WhileInThisCardRange` | 7 | `Frame-large-RangedInner` | `range` |
| `WhenEnteringThisCardRange` | 8 | `Frame-large-OnsetOpening` | `enter` |
| `WhenCardInRangeActivates` | 9 | `Frame-large-RecurringOpening` | `every-activate` |
| `WhenActivates` | 10 | `Frame-large-Opening` | `activate` |

这里不是猜的：把 54 个普通 trait 按 `TraitIdStr` 反推出来的 Frame，和它们英文名的
前缀（`Opening …` / `Lingering …` / `Ranged Inner …` …）**54/54 完全一致**，
且 11 个槽位正好用满 11 个非特例 Frame。

## 3. Icon：`spec.Icon` 选图案，`Effect0.TraitEffect` 选 active/passive

```text
92   mov    eax, 1FA0h
93   cmp    [rdi+8], ax                  ; Effect0.TraitEffect ? 0x1FA0
94   cmovb  r14, rbp                     ; < 0x1FA0 -> rbp = TraitEffectPassiveToIcon

252  cmp    byte ptr [rdi+1Ah], 0        ; EffectCount > 0 -> 图标 GameObject 才显示
273  movzx  r15d, [rsp+arg_10]           ; a3
275  test   r15b, r15b
276  jz     ...
277  cmp    dword ptr [r14+18h], 0       ; 长度 0 检查
278  lea    rdx, [r14+20h]               ; a3 -> m_Items[0]（默认空图标）
280  movzx  eax, byte ptr [rdi+1Bh]      ; eax = spec.Icon
281  cmp    eax, [r14+18h]               ; 越界检查
283  lea    rdx, [rax+4]
284  lea    rdx, [r14+rdx*8]             ; rdx = &m_Items[spec.Icon]
291  call   Constrained2D._irA(icon, [rdx])
```

伪代码：

```csharp
bool active = spec.Effect0.TraitEffect >= 0x1FA0;
Material[] icons = active ? a.TraitEffectActiveToIcon : a.TraitEffectPassiveToIcon;
icon.SetActive(spec.EffectCount > 0);
icon.material = icons[spec.Icon];
```

- `0x1FA0 = 8096`。`TraitEffect` 是 `ushort`，只有两个「瞬时」效果跨过这条线：
  `8096 = 造成伤害`、`8097 = 治疗`（`0x4CEB80` 的 `_XH._fpA`：`8096→3, 8097→2`；
  `0x4B36C6` 起的执行器对这两个值分别走掉血 / 回血分支）。
- 因此 **`-active` = 该 trait 的首个效果是伤害或治疗（瞬时触发）**，`-passive` = 其它
  （力量/毅力百分比、增减益等持续效果）。这也和 `PlayerTraitIconContainer` 里
  `colorToPassiveAnimations` / `colorToTriggerAnimations` 的命名一致。
- `spec.Icon` 是 0..16 的枚举（17 个槽位），槽位 0 是「空/默认」图标
  （`_QsA()` 清空时就是取 `[0]`）。实际出图 15 个。
- 其中 `Icon-ChromaticIsolation.webp` 是**只有一张图**的特例：没有 `-active` /
  `-passive` 两态，只给 `Ranged Chromatic Isolation: Red`（TraitId 66）用，
  该 trait 的 Frame 是 `RangedInner`、`Tier = 0`（不显示 tier 指示器）。
  说明这两个状态槽位指向同一张纹理，或者该 trait 只会以其中一种状态渲染。

### 枚举值 → 素材名这一层需要资产

`spec.Icon` 是策划在 `GameData.asset` 里手填的，代码里没有任何把数字翻译成
`Aegis` / `Surge` 的表，`dump/export/stringliteral.json` 里也搜不到素材名。
**17 个槽位和 15 个图片文件名的对应关系只能从资产里读**：

```text
GameData.asset（MonoBehaviour）
  traitIndexToName[i]  -> 字符串 id，和 data/trait.json 的 TraitIdStr 对应
  traits[i].Effect0.TraitEffect / TraitActivationCondition / EffectCount
  traits[i].Icon       -> 0..16
  traits[i].Tier       -> 0..3（0 = 不显示 tier）
```

拿到之后，`traits[i].Icon == n` 的这批 trait，它们的英文名后缀就是槽位 `n` 的名字
（`Inner Aegis` → Aegis，`Opening Surge` → Surge …），一次就能把 17→15 的表反解出来。

导出方法和 `dump/MonoBehaviour/DynamicStringMapping.json` 同一套（AssetRipper 选
`GameData` 这个 ScriptableObject 导成 JSON）。Unity 会把上面这些字段写成
`traits[]` / `traitIndexToName[]`，枚举和 `byte` 都是整数。

## 4. Tier

```text
302  cmp    byte ptr [rdi+1Ch], 0        ; Tier > 0
306  movzx  eax, byte ptr [rdi+1Ch]
307  cmp    eax, [rsi+18h]               ; Tier <= 数组长度
308  setle  bpl
412  movzx  edx, byte ptr [rdi+1Ch]
413  dec    rdx
418  mov    rdx, [rsi+rdx*8+20h]         ; TraitTierTo{Small|Large}Icon[Tier-1]
```

即 `Tier-1` 索引 `trait-tierindicator-large-0N-both`（`Tier` 为 0 时整个指示器隐藏），
另外 `tierIndicatorLarge` 的 Y 偏移 = `ActivationConditionToTierLargeIconYOffset[Effect0.TAC]`。

`Tier = 0` 这条分支有实测佐证：66 号 `Ranged Chromatic Isolation: Red` 就是没有 tier 角标的
trait，和 `setle` / `Tier > 0` 的两道判断一致。`Tier` 超过数组长度时指示器也会隐藏。

## 5. 尺寸 / 变体（不影响纹理文件名）

`TraitIcon.style`（`TraitIcon._BI`，0..3，Prefab 里配的）：

| style | Frame 显示 | Frame 数组 | Tier 指示器 |
| --- | --- | --- | --- |
| 0 | 隐藏 | — | Small |
| 1 | 隐藏 | — | Large |
| 2 | 显示 | `ActivationConditionToSmallFrame` | Small |
| 3 | 显示 | `ActivationConditionToLargeFrame` | Large |

`_qsA` 的第二个 `bool`（`a4`）= 用 `*Mini` 那一套素材。`style` / `mini` 只决定
「用哪个 Material 槽」，文件名层面没有区分：`data/trait/` 里只有一套
`Frame-large-*`，说明 small / mini 的 Material 复用的是同一批纹理（只改缩放和
Shader 参数）。如果以后发现 small 的贴图不一样，那就是这套 Material 指向了另一张图。

## 6. 落地：`tools/trait_icons.py`

```bash
python tools/trait_icons.py            # 从 TraitIdStr / 英文名反推 -> data/trait-icon.json
```

- 普通 trait（`damage-efficacy-activate-t1` 这类，64 个）：Frame 从触发条件词、Icon 从效果族词、
  active/passive 从「是否伤害/治疗」得到，Frame + Icon 全部确定
  （`denominator-power` 族按 `Weaken` 出图）。结果是 34 个 `-active`、30 个 `-passive`。
- `unique-*`（52–56、65–68，9 个）：id 里既没有条件词也没有效果词，只能从英文名拆。
  Frame 可信（名字就是 `<Frame> <Icon>` 格式）；active/passive 需要 `GameData` 才能定，
  其中 66 已有确定结论（`RangedInner` + `Icon-ChromaticIsolation` + 无 tier）。
- id 1 `unique-trait` 是 `EffectCount == 0` 的占位（游戏显示空框、隐藏图标）。
