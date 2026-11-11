# Body-family review (independent)

This review covers the current portraits in `frontend/assets/species/`: 50 art IDs in male and female presentations. The androgynous set was not reviewed. Bariaur has no portraits or catalog rows in this checkout. Machine-readable version: `data/body-families.json`. The canonical audit (`tools/2d-assets/`) is absent from this checkout and was not changed.

## Facts observed in the art

- **Merfolk and Yuan-ti have legs** in both presentations. Yuan-ti also has a tail.
- **Satyr is bipedal**, with goat legs and hooves.
- **Kenku has no wings**: arms with clawed hands, plus talon feet.
- **Aarakocra's arms are the wings**, with clawed hands at the wing joint. This is the hardest case for sleeves, gauntlets and grips.
- **Fairy has separate back wings** and an airborne pose with feet off the ground.
- **Tails:** Dragonborn, Kobold, Lizardfolk, Minotaur, Sahuagin, Tabaxi, Tiefling, Yuan-ti.
- **Shell:** Tortle only. Back items (cloak, quiver, back banner) conflict with the shell.
- **Effects already painted into the base art:**
  - Aasimar: halo.
  - Kalashtar: psychic spirit aura.
  - Changeling: a second face.

  Class effects layered on these need a check so the same idea isn't doubled (halo + radiant, Kalashtar + psychic shimmer).
- **Base clothing differs by presentation:** most female portraits wear long skirts, while male portraits wear trousers and boots. The male Githzerai wears a floor-length robe. Lower-body armor must cover or mask the base skirt. This is driven by the base clothing, not by anatomy.
- **Footwear falls into groups:**
  - Booted
  - Bare plantigrade
  - Digitigrade paw/claw
  - Talon
  - Webbed
  - Root-like (Mandrake)
  - Hoof (Minotaur, Satyr)
  - Quadruped hoof
  - Airborne (Fairy)

  Genasi and Dragonborn differ by presentation: booted when male, bare when female.
- **All portraits already wear travel clothes.** Wardrobe 1 can reuse the base portrait instead of needing a new export. The estimate assumes this.

## Proposed corrections (not applied)

| Species | Baseline | Proposal | Confidence |
|---|---|---|---|
| Warforged | broad | broad (male), standard/tall (female): the female portrait is slender | high |
| Gith | one entry | two art IDs (`githyanki`, `githzerai`), both standard/tall | high |
| Mandrake | small/slender | test against standard/tall: long-limbed, adult proportions | medium |
| Goblin | small/slender | keep, but test an overlay: torso and limbs look close to standard | low |
| Fairy | small/slender | keep, and add an airborne-pose flag for leg armor and back items | high |
| Aarakocra | standard/tall | keep, and add a wing-arm component variant (sleeves, gauntlets, grips) | high |
| Satyr | standard/tall | keep, and add hoofed lower legs; share lower-leg pieces with Minotaur | high |
| Centaur + Bariaur | quadrupedal humanoid | keep as one family. Upper body may share with standard/tall; barding needs equine and caprine exports | n/a |

## Reuse opportunities

- Treat tails, horns or tall ears, wings, shell and footwear as **component variants** (openings, cut-outs, alternate boots), not as reasons to duplicate an outfit.
- Robes (`wardrobe.arcane-robes`) hide the lower body, so they may fit several families with one export.
- **Props are fitted per grip and pose**, then scaled per family. Small-family hands may need a check, but not a repaint by default.
- **Creature assets (bear, wolf, steel defender, cannon, skeleton, hound, warhorse) are independent of species and presentation.** Only Form of the Beast and Lycan hybrids are character-specific.
- **The Cavalier warhorse is drawn standing alongside the character, never ridden.** A humanoid riding pose is impossible for Centaur and Bariaur, and the catalog does not require riding art.
