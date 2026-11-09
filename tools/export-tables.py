import json
from pathlib import Path

with Path("dump/MonoBehaviour/DynamicStringMapping.json").open(encoding="utf-8") as f:
    dm = json.load(f)


def dump(
    field: str,
    filename: str,
    field_name: str,
    value: str = "IdValues",
):
    tm = dm[field]

    ids = (i["Value"] for i in tm["Ids"])
    values = tm[value]

    items = [{field_name: item_id, "Name": body} for item_id, body in zip(ids, values)]
    with Path(f"data/{filename}.json").open("w", encoding="utf-8") as f:
        json.dump(
            items,
            f,
            ensure_ascii=False,
            indent=4,
        )


def dump_recipes():
    recipe_name = dm["recipeIdTypeMapping"]

    ids = (i["Value"] for i in recipe_name["Ids"])
    names = recipe_name["IdValues"]
    named_ids = recipe_name["IdStr"]

    recipes = [
        {
            "CardBaseId": card_base_id,
            "CardBaseIdStr": named_id,
            "Name": name,
        }
        for card_base_id, named_id, name in zip(ids, named_ids, names)
    ]
    with Path("data/recipe.json").open("w", encoding="utf-8") as f:
        json.dump(
            recipes,
            f,
            ensure_ascii=False,
            indent=4,
        )


def dump_traits():
    trait_name = dm["traitNameTypeMapping"]
    trait_desc = dm["traitDescriptionTypeMapping"]

    ids = (i["Value"] for i in trait_name["Ids"])
    names = trait_name["IdValues"]
    named_ids = trait_name["IdStr"]
    descs = trait_desc["IdValues"]

    traits = [
        {
            "TraitId": trait_id,
            "TraitIdStr": named_id,
            "Name": name,
            "Description": desc,
        }
        for trait_id, named_id, name, desc in zip(ids, named_ids, names, descs)
    ]
    with Path("data/trait.json").open("w", encoding="utf-8") as f:
        json.dump(
            traits,
            f,
            ensure_ascii=False,
            indent=4,
        )


dump("iotaTitleTypeMapping", "iota", "IotaId", "IdStr")
dump_recipes()
dump_traits()
