"""Schema of ``ifapp.Game.Data.SingleFileSaveDataV2`` and everything it contains.

Member order and wire types were taken from the generated ``Serialize`` methods
in ``GameAssembly.dll`` (IL2CPP), not guessed from field layout.  A save file
produced by the game decodes to exactly its last byte with this schema.
"""

from .model import (
    BOOL,
    F64,
    I16,
    I32,
    I64,
    STRING,
    U8,
    U16,
    U32,
    U64,
    ArrayOf,
    DictOf,
    Enum,
    FixedArray,
    IotaPackedField,
    Object,
    UnmanagedStruct,
    UnorderedList,
)

# ---------------------------------------------------------------------------
# Enums (only those whose values are meaningful in save data)
# ---------------------------------------------------------------------------

CardColorType = Enum(
    "CardColorType",
    I32,
    {
        0: "Colorless",
        1: "Red",
        2: "Yellow",
        3: "Green",
        4: "Blue",
        5: "Purple",
    },
)

ChartDifficultyFlag = Enum(
    "ChartDifficultyFlag",
    U8,
    {
        0: "None",
        1: "Minimal",
        2: "Evolved",
        4: "Ultimate",
        8: "Forbidden",
    },
)

GameResultLamp = Enum(
    "GameResultLamp",
    U8,
    {
        0: "None",
        1: "Fail",
        2: "Clear",
    },
)

GameResultClear = Enum(
    "GameResultClear",
    U8,
    {
        0: "None",
        1: "DiveFailed",
        2: "DiveCleared",
        3: "FullLink",
        4: "PerfectDive",
    },
)

EncounterResultSuccessType = Enum(
    "EncounterResultSuccessType",
    I32,
    {
        0: "None",
        1: "AssistMode",
        2: "Real",
    },
)

CharacterIdentifier = Enum(
    "CharacterIdentifier",
    U8,
    {
        0: "Nia",
        1: "Mei",
        2: "Ayame",
        3: "Iris",
        4: "Story",
        5: "Freya",
        6: "Touko",
        7: "Keats",
        8: "Io",
        9: "Hana",
        10: "Raine",
        11: "Wren",
        12: "Aria",
        13: "Fell",
        14: "Extras",
        15: "GhostMan",
        16: "Lily",
        17: "Lynn",
        18: "Mireille",
        19: "Jeremy",
        20: "House",
        21: "GhostManFemale",
        22: "GhostManMale",
        23: "GhostManStudent",
        24: "Helvi",
        25: "Tsuru",
    },
)

SongSelectSortType = Enum(
    "SongSelectSortType",
    I32,
    {
        0: "SongAscending",
        1: "SongDescending",
        2: "ArtistAscending",
        3: "ArtistDescending",
        4: "LevelAscending",
        5: "LevelDescending",
        6: "RankAscending",
        7: "RankDescending",
        8: "ClearAscending",
        9: "ClearDescending",
    },
)

# ---------------------------------------------------------------------------
# Blittable structs (written as raw memory; ``.size`` is sizeof(T))
# ---------------------------------------------------------------------------

JudgementTypeCount = UnmanagedStruct(
    "JudgementTypeCount",
    16,
    [
        ("None", 0, U16),
        ("Miss", 2, U16),
        ("NearEarly", 4, U16),
        ("NearLate", 6, U16),
        ("PerfectEarly", 8, U16),
        ("PerfectLate", 10, U16),
        ("Shiny", 12, U16),
    ],
)

BattleScore = UnmanagedStruct(
    "BattleScore",
    56,
    [
        ("TotalDamagePlayerDealt", 0, F64),
        ("TotalDamageOpponentDealt", 8, F64),
        ("PlayerEgoRecovered", 16, F64),
        ("OpponentEgoRecovered", 24, F64),
        ("DifficultyRatingD", 32, F64),
        ("TypeModifier", 40, F64),
        ("NumberOfNotesJudged", 48, I32),
        ("TotalNoteCount", 52, I32),
    ],
)

CardInstance = UnmanagedStruct(
    "CardInstance",
    64,
    [
        # unique id per a card
        ("CardId", 0, I32),
        # Recipe Id
        ("CardBaseId", 4, I32),
        ("TierIndex", 8, U8),
        ("IsSR", 9, U8),
        ("CardColorType", 12, CardColorType),
        ("BasePower", 16, F64),
        ("BaseFortitude", 24, F64),
        # Left Range, -4 ~ 0
        ("BaseRangeOffsetStart", 32, I32),
        # Right Range, 0 ~ 4
        ("BaseRangeOffsetEnd", 36, I32),
        # TraitSlotType1..3 use the game's `_WH` enum (0..4). Only 0 and 3 occur
        # in this save; the gameplay meaning of each value is not yet documented.
        ("TraitSlotType1", 40, I16),
        ("TraitSlotType2", 42, I16),
        ("TraitSlotType3", 44, I16),
        ("TraitId1", 46, I16),
        ("TraitId2", 48, I16),
        ("TraitId3", 50, I16),
        # Unix timestamp, creation time
        ("SecondsSinceEpochUtc", 52, U64),
    ],
)

SavedDeck = UnmanagedStruct(
    "SavedDeck",
    24,
    [
        ("CardIds", 0, FixedArray(I32, 5)),
        ("Assigned", 20, BOOL),
    ],
)

EncounterResult = UnmanagedStruct(
    "EncounterResult",
    72,
    [
        ("EncounterId", 0, I32),
        ("BattleScore", 8, BattleScore),
        ("Success", 64, BOOL),
        ("SuccessType", 68, EncounterResultSuccessType),
    ],
)

IotaInstance = UnmanagedStruct(
    "IotaInstance",
    16,
    [
        # unpacked to BaseIotaId / Potency / TraitCount in JSON
        ("BaseIotaIdPotency", 0, IotaPackedField()),
        ("TraitId1", 4, I16),
        ("TraitId2", 6, I16),
        ("TraitId3", 8, I16),
        ("UserData", 10, U16),
        ("Count", 12, U16),
    ],
)

GameResultV4 = UnmanagedStruct(
    "GameResultV4",
    96,
    [
        ("SongId", 0, U16),
        ("Difficulty", 2, ChartDifficultyFlag),
        ("Lamp", 3, GameResultLamp),
        ("CalculatedResultClear", 4, GameResultClear),
        ("MaxCombo", 6, U16),
        ("CalculatedPaceValue", 8, I16),
        ("TapCounts", 10, JudgementTypeCount),
        ("HoldCounts", 26, JudgementTypeCount),
        ("SkyAreaCounts", 42, JudgementTypeCount),
        ("FlickCounts", 58, JudgementTypeCount),
        ("PlayerScore", 80, U64),
        ("SecondsSinceEpochUtc", 88, U64),
    ],
)

StoryEntryStateV5 = UnmanagedStruct(
    "StoryEntryStateV5",
    16,
    [
        ("StoryIdentifier", 0, U32),
        ("MaxLineCountRead", 4, I32),
        ("IsRead", 8, BOOL),
        ("HasPlayedSongChallenge", 9, BOOL),
        ("HasAllowedFastForwardSkipping", 10, BOOL),
        ("LastQuitLineCountRead", 12, I32),
    ],
)

Hex = UnmanagedStruct(
    "Hex",
    8,
    [
        ("Q", 0, I16),
        ("R", 2, I16),
        ("S", 4, I16),
    ],
)

IotaDropTableState = UnmanagedStruct(
    "IotaDropTableState",
    8,
    [
        ("Value", 0, U64),
    ],
)

RecipeFilterParameters = UnmanagedStruct(
    "RecipeFilterParameters",
    20,
    [
        ("TierFilter", 0, I32),
        ("ColorFilter", 4, I32),
        ("IncludeTypeColorChanges", 8, BOOL),
        ("TraitFilter", 12, I32),
        ("MasteryProgressFilter", 16, I32),
    ],
)

IotaFilterParameters = UnmanagedStruct(
    "IotaFilterParameters",
    8,
    [
        ("ColorFilter", 0, I32),
        ("TraitFilter", 4, I32),
    ],
)

CardFilterParameters = UnmanagedStruct(
    "CardFilterParameters",
    12,
    [
        ("TierFilter", 0, I32),
        ("ColorFilter", 4, I32),
        ("TraitFilter", 8, I32),
    ],
)

# ---------------------------------------------------------------------------
# Header-bearing structs (written member by member with a count header)
# ---------------------------------------------------------------------------

SongInfoMapping = Object(
    "SongInfoMapping",
    2,
    [
        ("BaseName", STRING),
        ("SongId", U16),
    ],
    nullable=False,
)

GameResultKey = Object(
    "GameResultKey",
    3,
    [
        ("BaseName", STRING),
        ("SongId", U16),
        ("Difficulty", ChartDifficultyFlag),
    ],
    nullable=False,
)

RecipeSaveDataV2 = Object(
    "RecipeSaveDataV2",
    17,
    [
        ("RecipeIdStr", STRING),
        ("RevealedHexes", ArrayOf(Hex, "HashSet<Hex>")),
        ("RevealedSafeHexes", ArrayOf(Hex, "HashSet<Hex>")),
        ("DefaultRevealedSafeHexCount", I32),
        ("RemainingSafeHiddenHexes", ArrayOf(Hex, "HashSet<Hex>")),
        ("BonusAreasSeen", ArrayOf(STRING, "List<string>")),
        ("BonusAreasRevealed", ArrayOf(STRING, "List<string>")),
        ("RevealedBonusAreaBasePower", I32),
        ("RevealedBonusAreaBaseFortitude", I32),
        ("RevealedRangeStartAmount", I32),
        ("RevealedRangeEndAmount", I32),
        ("RevealedTraits", ArrayOf(I16, "List<TraitId>")),
        ("challengeCompleteFlags", I32),
        ("intuitionProgress", I32),
        ("currentRecipeRandomSeed", I32),
        ("hasEverCrafted", BOOL),
        ("IslandAreasRevealed", ArrayOf(I32, "List<int>")),
    ],
    nullable=False,
)

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

CardInventory = Object(
    "CardInventory",
    3,
    [
        ("allCards", UnorderedList(CardInstance)),
        ("EncounterIdToSavedDeck", ArrayOf(SavedDeck)),
        ("LastUsedDeckIndex", I32),
    ],
)

IotaInventory = Object(
    "IotaInventory",
    2,
    [
        ("allIota", UnorderedList(IotaInstance)),
        (
            "obsolete_ExistsBaseIotaIdPotency",
            ArrayOf(IotaInstance, "HashSet<IotaInstance>"),
        ),
    ],
)

GameResultsSongInfoMapping = Object(
    "GameResultsSongInfoMapping",
    3,
    [
        ("Mappings", ArrayOf(SongInfoMapping, "SongInfoMapping[]")),
        ("HistoryIndexStart", I32),
        ("HistoryIndexLength", I32),
    ],
)

GameResultsV4 = Object(
    "GameResultsV4",
    4,
    [
        ("highscores", DictOf(GameResultKey, GameResultV4)),
        ("history", UnorderedList(GameResultV4)),
        ("songInfoMapping", UnorderedList(GameResultsSongInfoMapping, ref=True)),
        ("updateId", I64),
    ],
)

EncounterResults = Object(
    "EncounterResults",
    2,
    [
        ("results", UnorderedList(EncounterResult)),
        ("updateId", I64),
    ],
)

StoryStateV5 = Object(
    "StoryStateV5",
    2,
    [
        ("storyToState", DictOf(U32, StoryEntryStateV5)),
        ("updateId", I64),
    ],
)

GeneralSaveStateV5 = Object(
    "GeneralSaveStateV5",
    17,
    [
        ("SelectedCharacter", CharacterIdentifier),
        ("PackIdToSelectedSongId", DictOf(U16, U16)),
        ("LastSelectedPackId", U16),
        ("LastSelectedDifficulty", ChartDifficultyFlag),
        ("LastSelectedSongSelectSortType", SongSelectSortType),
        ("LastSecondarySortType", SongSelectSortType),
        ("LastSelectedEncounterId", I32),
        ("LastSelectedRecipeFilterParameters", RecipeFilterParameters),
        ("LastSelectedIotaFilterParameters", IotaFilterParameters),
        ("LastSelectedCardFilterParameters", CardFilterParameters),
        ("LastSelectedRecipeId", I32),
        ("TutorialFlags", U64),
        ("EnabledAnyStoryFastForwardSkipping", BOOL),
        ("StoryChoiceToResult", DictOf(STRING, STRING)),
        ("SeenSongVideoIds", ArrayOf(STRING, "HashSet<string>")),
        ("LastSelectedScenarioSongDifficulty", ChartDifficultyFlag),
        ("AssistMode", BOOL),
    ],
    nullable=False,
)

RecipeSaveStateV2 = Object(
    "RecipeSaveStateV2",
    2,
    [
        ("saveData", DictOf(I32, RecipeSaveDataV2)),
        ("updateId", I64),
    ],
)

LootDropState = Object(
    "LootDropState",
    2,
    [
        ("dropStates", UnorderedList(IotaDropTableState)),
        ("updateId", I64),
    ],
)

GrantsSaveState = Object(
    "GrantsSaveState",
    2,
    [
        ("grants", U64),
        ("updateId", I64),
    ],
)

SingleFileSaveDataV2 = Object(
    "SingleFileSaveDataV2",
    9,
    [
        ("CardInventory", CardInventory),
        ("IotaInventory", IotaInventory),
        ("GameResults", GameResultsV4),
        ("EncounterResults", EncounterResults),
        ("StoryToState", StoryStateV5),
        ("GeneralSaveState", GeneralSaveStateV5),
        ("RecipeSaveState", RecipeSaveStateV2),
        ("LootDropState", LootDropState),
        ("GrantsSaveState", GrantsSaveState),
    ],
)

ROOT = SingleFileSaveDataV2
