# Tilesets (P15.1)

Drop a folder here — `data/tiles/<name>/` — and select it with
`TILESET_NAME = "<name>"` in `config.py` (or `LLM_RPG_TILESET=<name>`
in the environment). Any image the set does not provide falls back
to the built-in procedural sprite, so partial sets are fine.

## The contract

One PNG per terrain value, named exactly:

    grass.png forest.png mountain.png water.png road.png
    building.png cave.png swamp.png farmland.png rubble.png
    scorched.png bridge.png

Optional entity overrides in an `entities/` subfolder:

    entities/player.png            the player
    entities/<class>.png           e.g. guard.png, merchant.png,
                                   monster.png, brigand.png ...

Any square size works (16/32/48px) — images are scaled to the
game's tile size at load. CC0 packs (e.g. Kenney's roguelike
tiles) drop in after renaming.
