# Species portrait fit audit: reuse findings

This is an independent visual audit of the 49 roster groups in `backend/data/species-groups.json` (48 portrait sets plus the Custom Lineage symbol), each in three presentations: 147 entries and 145 unique image files. It was written without reading the canonical body-family audit and does not replace it. Every number below comes from hand-placed landmarks (precision about ±30 px, in original 1024×1536 coordinates). Check them on `contact-sheets/*.jpg` before acting on them.

**Not available:** Bariaur is absent from this checkout (main @ 94d8dc8), in both the roster and the asset folder. It is recorded under `unavailable` and was not added. **Not counted:** 17 image files in `frontend/assets/species/` that the roster does not reference (style tests, single-presentation legacy files, `githzerai-*`, `custom-lineage-*.png`). They are listed in `observations.json → meta.unreferencedImagesIgnored`.

## 1. Facts about the art that affect every reuse decision

1. **Every portrait fills the same frame.** A Gnome, Halfling or Goblin is drawn head-to-toe as tall as a Goliath (feet at y≈1450-1490 in all of them). "Small" species differ in proportion, not in pixel height. A shared layer can't simply be scaled down: it has to be re-placed vertically. The Gnome shoulder line sits about 150-180 px lower than Human, Harengon about 145 px (tall ears), Fairy 95-125 px, Goblin, Grung and Kobold 60-80 px, and Dwarf 45-60 px.
2. **No portrait shows a cylindrical grip.** Of the 288 wrist/hand records, 243 are empty (hanging, clasped, on hip, touching the face or chest, palm up), 36 are hidden (pockets, behind the back, arms crossed), 8 hold cloth (cloak edge, lapel, scarf, shawl) and 1 holds its own forearm (Centaur androgynous). Any weapon, staff or tool layer needs a repainted grip hand or a separate grip-hand overlay for every species and presentation. No existing hand can be reused as a grip.
3. **Poses differ within a species**, so a male-fit layer often misses the female or androgynous arm even when the anatomy is the same. Examples: Centaur male arms crossed vs female hand at hair; Kalashtar hands clasped vs Human hands hanging; Geppettin male arm extended.
4. **Mirrored anatomy between presentations.** Several presentations show a one-sided feature on the opposite side of the image from the male, so any layer that respects it must be flipped or redrawn:
   - Tortle: shell on the image-left for male and female, image-right for androgynous.
   - Tails: Tabaxi, Minotaur, Dragonborn, Yuan-ti and Tiefling androgynous are flipped vs male; Lizardfolk male is flipped vs female/androgynous; Sahuagin female is flipped vs the others.

## 2. Anatomical differences vs differences in existing clothing

Many visible male vs female gaps are **clothing, not anatomy**. Most female presentations wear long skirts that hide hips and knees (recorded as `occluded`, never estimated). The underlying leg anatomy is presumably the same, but that is unconfirmed, so lower-body fit for those presentations is lower-confidence.

| Kind | Cases |
|---|---|
| Real anatomical difference between presentations | **Warforged**: male bulky (~460 px shoulders); female slender (~330 px, sash-waist ~200 px wide, sculpted breastplate, narrow pointed feet); androgynous close to the female in limb and shoulder width. **Dwarf**: beard on the male only (covers the chest to y≈600). **Tortle androgynous**: shell on the other side. **Aarakocra**: female and androgynous wing spans and torsos narrower; androgynous wing hugs the arm. **Ruinbound**: growths in different places on each (male whole image-left arm; female collarbone/hand; androgynous shoulder + shin). Shoulder width ratios (female/male): Orc 0.80, Goliath 0.73, Minotaur 0.67, Bugbear 0.83, Tabaxi 0.62, Dragonborn 0.70, Warforged 0.72. Part of the gap is clothing (the Goliath male's fur mantle widens the silhouette), but the limbs are visibly thinner too. |
| Clothing-only difference (anatomy appears the same) | **Dragonborn male** wears human-shaped boots. Female and androgynous show clawed dragon feet, so the boot hides anatomy and is not evidence of human feet. Genasi, Goliath and Verdan female are barefoot while male wears boots (or vice versa). Skirts: Human, Dwarf, Halfling, Orc, Bugbear, Goblin, Kobold, Tortle, Gnoll, Mandrake, Minotaur, Tabaxi, Warforged and most of the remaining roster. Hoods/capes on the Dwarf male and Halfling androgynous hide the shoulder outlines. |

## 3. What can plausibly share artwork

Groups are suggestions. A shared group means "the same base art with at most a translate/scale", not proof of fit.

### Shared with little or no change
- **Human-proportion bipeds**: Human, Half-Elf, Khoravar, Changeling, Shifter, Reborn, Kalashtar, Genasi, Tiefling (with a tail opening), Ruinbound (minus growth cut-outs), Hexblood, Dhampir, Elf, Duskling, Gith, Aasimar, Yuan-ti (with a tail opening) and Triton (barefoot). Shoulder lines fall within about 300-350 px of each other and waists within ±40 px. Torso, sleeve and lower-body art can share one base, with a slim variant for Elf, Gith, Dhampir male and Aasimar.
- **Human upper body on non-human legs**: Satyr and Centaur share human torso and sleeve art from the waist up. Satyr needs caprine-leg lower garments; Centaur needs equine barding.
- **Heavy plantigrade bipeds**: Orc male, Goliath male/androgynous, Half-Orc male, Hobgoblin male, Firbolg, Minotaur male and Warforged male (with plates) can share a broad/heavy torso base (430-480 px shoulders).

### Same art, different placement
- **Small large-headed bipeds**: Gnome, Halfling, Goblin and Geppettin. Torso width is close to Human (360 ± 30 px) but the shoulder line is 50-180 px lower and legs are 600-715 px long (Human 750-820). The same garment design needs vertical re-placement and a shorter lower-body piece, so treat it as a placement-variant group, not separate construction.
- **Dwarf**: a wide, low torso (shoulders +45-60 px lower, 1.16-1.47× width) and short legs (610-715 px). The male also needs a beard-over layer.
- **Harengon**: a standard-width torso placed about 145 px lower (tall ears push the head down). Lower body is digitigrade with long feet.
- **Bugbear and Kenku**: hanging arms measure 550-570 px vs Human 475, so sleeves and gloves must extend about 70-90 px.

### Needs different construction
- **Back-occupying anatomy.** Closed-back shirts, capes, backpacks, quivers and back-slung weapons all collide on these:
  - Tortle shell: front panels and tabards with straps.
  - Aarakocra feathered wings: wing slots, and open or split sleeve backs.
  - Fairy insect wings: nearly full-frame span, low backs.
  - Sahuagin dorsal ridge.
- **Aarakocra wing-arm anatomy.** Arms are separate, feathered, with 4-digit talon hands. Wings root behind and above the shoulders and hang behind the arms to y≈1000-1100. In the male the primaries don't visibly attach to the forearm. In the androgynous the wing outline hugs the back of the arm, so attachment is ambiguous (confidence medium). Treat every Aarakocra sleeve as needing an open or split rear seam. Kenku is also avian but has no wings: sleeves need only the feathered-arm fit.
- **Digitigrade or hoofed legs.** Hock/raised ankle at y≈1250-1350 on Kobold, Gnoll, Tabaxi, Harengon, Minotaur and Satyr; Aarakocra and Kenku show an avian intertarsal joint at the cuff. Human trousers and boot shafts don't fit: these need their own lower-leg construction, and footwear is mostly impossible (hooves, paws, talons, hare feet).
- **Feet that can't take footwear, or where it would hide the species trait.** Grung (long webbed toes), Mandrake (root feet), Merfolk (webbed fin feet), Tortle (elephantine), Halfling (large hairy feet, a trait not a blocker), Fairy (hovering, no ground contact).
- **Irregular or segmented limb outlines.** Mandrake vines (plus shoulder flowers), Warforged plates (rigid segments), Geppettin ball joints (meant to stay visible), Merfolk and Sahuagin forearm/calf fins (tight sleeves clip them), Ruinbound growths.
- **Tail openings.** Kobold, Tabaxi, Minotaur, Dragonborn, Lizardfolk, Tiefling, Yuan-ti, Sahuagin and a small puff on Harengon and Satyr. Side flips by presentation (see §1.4).
- **Hands.** Non-human hand groups need their own glove and grip art: talon-4 (Aarakocra, Kenku), padded-4 (Grung), twig (Mandrake), mechanical (Warforged), wooden-jointed (Geppettin), webbed (Merfolk, Sahuagin), huge claws (Tortle), claws (Dragonborn, Lizardfolk, Gnoll, Tabaxi, Bugbear, Kobold).

## 4. Quadrupedal humanoid family (Centaur; Bariaur when available)

- **Upper body:** reusable from human torso and sleeve art. The torso has to stop at the human-equine junction (male ≈ y590-650; female/androgynous ≈ y500-560), which is tagged `torso.quadruped-junction.*`. Female and androgynous are slimmer (275-282 px vs 313 px). The female has elven ears and long hair to the waist, which affects capes and hoods.
- **Lower body:** a separate barding problem. Four hooves at roughly fore (256-411, 1363-1445) and hind (576-850, 1326-1354). Horse barrel extends to x≈900, tail x≈700-950. Nothing from biped lower-body art transfers.
- **Bariaur (not in checkout):** expected to reuse the same upper-body approach, with caprine barding that is not shared with equine barding. Verify against its own images when it lands.

## 5. Clearance hot spots (head and accessories)

| Concern | Species / presentation |
|---|---|
| Horns | Minotaur (widest, x≈120-800), Satyr (curled ram), Tiefling, Kobold, Dragonborn, Hexblood antler crown |
| Ears | Goblin (widest, x≈200-780), Verdan, Gnome, Firbolg (drooping), Harengon (to the top of the frame), Bugbear, Duskling, Gnoll, Shifter, Tabaxi |
| Wings | Aarakocra, Fairy |
| Tail | See §3; sides flip by presentation |
| Shell | Tortle (side flips for androgynous) |
| Hair | Dwarf braids, Centaur, Elf, Bugbear female long hair, Halfling/Gnome curls |
| Beard | Dwarf male (chest-length, hides torso-front detail), Gnome male (short) |
| Effects (not anatomy, but occupy space) | Aasimar halo, Kalashtar spirit (image-right), Changeling second face (image-right of head), Tiefling tail glow |
| Snout/beak/tusks | Aarakocra, Kenku, Kobold, Dragonborn, Lizardfolk, Gnoll, Minotaur (muzzle), Orc and Bugbear (tusks); closed helms need cut-outs |

## 6. Uncertainties

- Landmarks are hand-placed from a 0.4× view (zoomed for Centaur, Aarakocra, Fairy and Warforged), precision about ±30 px. 39 are marked `uncertain`, 188 `occluded` and 18 `not-applicable`; no occluded point has invented coordinates.
- Fairy legs cross and hover, so feet and some knees are uncertain. The Aarakocra androgynous wing attachment is ambiguous. The Khoravar male image-right hand is hidden behind the body.
- Torso width classes come from shoulder-to-shoulder distance on the drawn silhouette (sleeves and cloaks included). 68 of 144 fall within 20 px of a class threshold and are flagged `torsoGroupDerivation.borderline`.
- Female hips and knees under skirts are unobserved. Their lower-body groups assume the species anatomy seen in other presentations, which is an inference, not an observation.
- Nothing here was checked against an actual overlaid clothing layer. The validator checks data integrity only, not fit or grips.
