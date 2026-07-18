"""Crafting system — recipes turn ingredients into output items.

A recipe is keyed by output item id and lists required ingredients
(by item id and quantity), an optional gold cost, and an optional
required location property (e.g. "forge" only for weapons).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from items.item_registry import create_item, ITEM_REGISTRY

logger = logging.getLogger("llm_rpg.crafting")


@dataclass
class Recipe:
    output_id: str
    output_qty: int = 1
    ingredients: Dict[str, int] = field(default_factory=dict)
    gold_cost: int = 0
    required_property: Optional[str] = None  # e.g. "forge" -- location-keyed
    skill: str = "alchemy"  # which skill this recipe trains
    min_skill: int = 0      # M3: minimum level in `skill` to craft (tiered magic)

    def output_name(self) -> str:
        item = ITEM_REGISTRY.get(self.output_id)
        return item.name if item else self.output_id


# Recipe registry — loaded from data/recipes.json ------------------------

def _build_recipes() -> Dict[str, Recipe]:
    from items.data_loader import load_data_file
    out: Dict[str, Recipe] = {}
    for rid, entry in load_data_file("recipes.json").items():
        out[rid] = Recipe(
            output_id=entry.get("output_id", rid),
            output_qty=entry.get("output_qty", 1),
            ingredients=dict(entry.get("ingredients", {})),
            gold_cost=entry.get("gold_cost", 0),
            required_property=entry.get("required_property"),
            skill=entry.get("skill", "alchemy"),
            min_skill=entry.get("min_skill", 0),
        )
    return out


RECIPES: Dict[str, Recipe] = _build_recipes()


def list_recipes() -> List[Recipe]:
    return list(RECIPES.values())


def find_recipe(output_id: str) -> Optional[Recipe]:
    return RECIPES.get(output_id)


def _count_in_inventory(player, item_id: str) -> int:
    count = 0
    for it in player.inventory:
        iid = getattr(it, "id", "")
        if iid == item_id:
            count += getattr(it, "quantity", 1)
    return count


def _consume_from_inventory(player, item_id: str, qty: int) -> None:
    needed = qty
    new_inv = []
    for it in player.inventory:
        iid = getattr(it, "id", "")
        if iid == item_id and needed > 0:
            stack_qty = getattr(it, "quantity", 1)
            if stack_qty > needed:
                # Reduce in-place
                it.quantity = stack_qty - needed
                needed = 0
                new_inv.append(it)
            else:
                needed -= stack_qty
                # Drop this entry
        else:
            new_inv.append(it)
    player.inventory = new_inv


def can_craft(player, output_id: str,
              location_properties: Optional[Dict] = None) -> str:
    """Return empty string if craftable, otherwise a reason."""
    recipe = find_recipe(output_id)
    if not recipe:
        return f"No recipe for {output_id}."
    if recipe.gold_cost and player.gold < recipe.gold_cost:
        return f"You need {recipe.gold_cost}g (you have {player.gold})."
    for iid, qty in recipe.ingredients.items():
        if _count_in_inventory(player, iid) < qty:
            item = ITEM_REGISTRY.get(iid)
            iname = item.name if item else iid
            return f"You need {qty}x {iname}."
    if recipe.required_property:
        props = location_properties or {}
        if not props.get(recipe.required_property):
            return f"You need to be at a {recipe.required_property} to craft this."
    if recipe.min_skill:                          # M3 tiered magic crafting
        try:
            from engine.skill_progression import get_skill_level
            if get_skill_level(player, recipe.skill) < recipe.min_skill:
                return f"You need {recipe.skill} {recipe.min_skill}."
        except Exception:
            pass
    return ""


def craft(player, output_id: str,
          location_properties: Optional[Dict] = None) -> str:
    """Attempt to craft an item. Returns a status string."""
    err = can_craft(player, output_id, location_properties)
    if err:
        return err
    recipe = find_recipe(output_id)
    # Pay
    player.gold -= recipe.gold_cost
    for iid, qty in recipe.ingredients.items():
        _consume_from_inventory(player, iid, qty)
    # Produce
    new_item = create_item(recipe.output_id, quantity=recipe.output_qty)
    if not new_item:
        return f"Failed to produce {recipe.output_id}."
    player.inventory.append(new_item)
    return f"You craft {new_item.name}."
