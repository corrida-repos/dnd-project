# Class visual-recipe catalog

This catalog plans the art. For every class/subclass row in `backend/data/class-combos.json`, it records which shared wardrobe, pose, props, accessory kit, effects and companion or transformation should show the class while the character keeps its species look. It is planning data only. The frontend does not read it yet, and nothing here generates or fits images.

## Files

| Path | Contents |
|---|---|
| `data/selections.json` | One entry per class-combo row (270). Holds the rules facts (armor grants, restrictions, feature levels, sources, confidence, open questions) and a `visual` pointer to a recipe or alias. |
| `data/recipes.json` | 147 visual recipes (artistic defaults only) plus 28 explicit aliases for renamed or equivalent subclasses. |
| `data/components.json` | Shared component definitions: 7 wardrobes, 6 poses, 36 props, 15 accessory kits, 13 painted effect bases, 36 effect recolors, 8 signature layers and 19 creatures/transformations. |
| `data/class-rules.json` | Armor and shield training by class and ruleset, class restrictions (Monk, Rage, 2014 Druid metal) and the 2024 order options (Protector, Warden). |
| `data/sources.json` | Source registry, with free primary links where they exist (SRD 5.1/5.2). |
| `data/body-families.json` | Independent review copy of the provisional body families, per-component concerns seen in the current art, and proposed corrections. **It is not the canonical audit.** |
| `catalog.py` | Validator, dependency report, export estimate and table generator. Standard library only. |
| `tables/*.md` | Generated readable tables. Do not edit them by hand. |
| `body-family-review.md` | Task 3 write-up. |

## Commands

Run from the repository root:

```sh
python3 tools/visual-catalog/catalog.py validate        # add -v for info lines
python3 tools/visual-catalog/catalog.py report          # counts + per-component dependents (JSON)
python3 tools/visual-catalog/catalog.py estimate        # add --retry-factor 0.5 to see retries separately
python3 tools/visual-catalog/catalog.py tables          # regenerate tables/; --check fails if stale
python3 -m unittest discover -s tests/visual-catalog
```

## Model

- A **selection** is a rules identity: ruleset, class and subclass. Selections are never merged.
- A **recipe** is a visual identity. Several selections can point at one recipe directly (the same subclass in 2014 and 2024), or through an **alias** when the subclass was renamed. Examples: Way of Shadow → Warrior of Shadow, Purple Dragon Knight → Banneret, Aberrant Mind → Aberrant Sorcery. Aliases can chain. The validator rejects cycles and missing targets.
- Recipes hold **artistic defaults** only. Rules facts live on selections and in `class-rules.json`. The validator checks each recipe's wardrobe and props against the rules of every selection that uses it:
  - Armor category against class training, plus subclass grants, plus any class option the recipe explicitly lists in `ruleAssumptions`. Example: the 2024 War Domain wears heavy plate only by assuming Divine Order: Protector.
  - Shields against shield training.
  - Monk and College of Dance unarmored requirements, Rage in heavy armor, the 2014 Druid metal convention, and Bladesong (no medium/heavy armor, no shield, no two-handed weapon).
  - Species restrictions, such as the SCAG Battlerager being dwarf-only, are reported but not enforced.
- **Effects** are recolors (`tint`) of 13 painted bases. Recolors and mask-derived auras count as deterministic work, not new designs.
- **Creatures** come in four kinds:
  - `shared-creature`: looks the same for every character; one export.
  - `overlay-fitted`: layered over the character; one fit per body family.
  - `composition`: a deterministic transform of the composed character (Giant's Might, Invoke Duplicity).
  - `hybrid-character`: a repaint per species and presentation (Form of the Beast, Lycan). These are flagged as expensive.

## What validation cannot tell you

Metadata checks cannot show that a layer fits a body or that a grip looks right. A body-family assignment does not prove PNG compatibility. The estimate counts reachable recipe/component/fit combinations under stated assumptions. It does not multiply every component by every species, presentation and pose.

## Evidence levels

- `facts` and `featureLevels` carry a source ID and a confidence. None were re-read against source text in this session: outbound access to dndbeyond.com and the other rules sites was blocked. Confidence reflects how well-established the rule is.
- Third-party subclasses (Mage Hand Press, Exploring Eberron), plus the Arcana Unleashed and Heroes of Faerûn rows, have unreviewed rules. Their recipes are marked `low` and list the open question. Their cues are artistic placeholders, not rules claims.

## Sorrow Knight

- **Row:** 5.5E Fighter, `5.5e Expanded Rules`, sources `Player's Handbook (2024)` + `D&D Beyond Drops`, `Spell-less`.
- **Ratings:** copied unchanged from 5.5E Champion as an editorial Fighter baseline. These are not published rules.
- **Suggested adjustment, not applied:** Control 2 → 3. Secondary coverage describes it as debuff-heavy (frightening on teleport, despair-themed strike options). Revisit after reading the official text.
- **Visual:** reuses Champion's heavy plate and greatsword. New art is limited to one additive layer (`sig.sorrow-knight-shroud`) and a recolor of the smoke-wisp base (`fx.shadowfell-mist`).
