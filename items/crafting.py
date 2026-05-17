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

    def output_name(self) -> str:
        item = ITEM_REGISTRY.get(self.output_id)
        return item.name if item else self.output_id


# Recipe registry --------------------------------------------------------

RECIPES: Dict[str, Recipe] = {
    "potion": Recipe(
        output_id="potion",
        ingredients={"herb_bundle": 1},
        gold_cost=5,
    ),
    "greater_potion": Recipe(
        output_id="greater_potion",
        ingredients={"herb_bundle": 3, "potion": 1},
        gold_cost=10,
    ),
    "bandage": Recipe(
        output_id="bandage",
        ingredients={"wolf_pelt": 1},
        gold_cost=1,
    ),
    "sword": Recipe(
        output_id="sword",
        ingredients={"coins": 3},
        gold_cost=20,
        required_property="forge",
    ),
    "iron_shield": Recipe(
        output_id="iron_shield",
        ingredients={"shield": 1, "coins": 2},
        gold_cost=25,
        required_property="forge",
    ),
    "silver_blade": Recipe(
        output_id="silver_blade",
        ingredients={"sword": 1, "troll_tooth": 1, "stolen_jewelry": 1},
        gold_cost=100,
        required_property="forge",
    ),
}


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
