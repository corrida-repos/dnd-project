# Species portrait fit observations

An independent visual fit audit of the species portraits. These are analysis artifacts only: nothing here is app artwork, nothing changes the source portraits, and nothing here is the canonical asset pipeline (that is owned elsewhere).

The roster and image paths come from `backend/data/species-groups.json`: 49 groups × male/female/androgynous = 147 entries. Bariaur is not in this checkout and is recorded under `unavailable`. Image files the roster does not reference are listed but not counted as species.

| File | What it is |
|---|---|
| `inspection-notes.txt` | One line per species/presentation, written while viewing each portrait on a labelled coordinate grid. This is the only source of landmarks. |
| `annotations.py` | Hand-authored anatomy, fit groups, clearance concerns and per-presentation differences. |
| `observations.json` | Per species/presentation: anatomy and limb topology; suggested torso, lower-body, sleeve, hand and footwear groups; differences from the male baseline (anatomical vs existing clothing); clearance; source size and SHA-256; inspection method and confidence. |
| `landmarks.json` | Shoulders, elbows, wrists (with hand state and grip category), waist line, hips, knees, feet and extra digitigrade/avian joints and hooves, in original pixels. Each point has an explicit status: `visible`, `uncertain`, `occluded`, `not-applicable` or `uncertain-unlocated`. Non-visible points have `null` coordinates. |
| `reuse-findings.md` | Which pieces can share art, which need placement changes, and which need different construction. |
| `contact-sheets/<group>.jpg` | Landmark overlays for review (1/3 scale). |
| `build.py`, `notes_parser.py`, `contact_sheets.py` | Regenerate the JSON and the sheets from the notes. |
| `validate.py` | Integrity checks (see below). |
| `test_validate.py` | Proves the validator catches bad hashes, out-of-bounds or invented coordinates, and missing roster entries. |

## Commands (from the repository root)

```sh
python3 tools/visual-catalog/fit-observations/build.py        # regenerate JSON + contact sheets (needs Pillow)
python3 tools/visual-catalog/fit-observations/validate.py     # exit 1 on errors
python3 -m unittest discover -s tools/visual-catalog/fit-observations -p 'test_*.py'
```

## Conventions

- Coordinates are original image pixels, origin top-left, 1024×1536 for every PNG.
- `imageLeft` means the viewer's left, which is the character's right side.
- Points were placed by eye from a 0.4× grid view, plus zoomed crops for Centaur, Aarakocra, Fairy and Warforged. Precision is about ±30 px.
- The waist is a horizontal line (`y` only), read from the belt, sash or bodice, so it depends on the clothing.
- `cylindricalGrip` is `false` everywhere: no portrait holds a cylindrical prop. Wrist records separate empty hands, hidden hands, and hands holding cloth or the character's own arm.
- Torso groups are computed from shoulder width (slim/standard/broad/heavy) plus a back modifier (shell, wings, dorsal fin, quadruped junction). Vertical differences are reported as `placementVsHumanMale` offsets, not as separate groups.

## What the validator checks and what it does not

It checks: source paths against the roster, SHA-256 and dimensions against the files on disk, that every roster entry appears exactly once in both JSON files, that unavailable species are not marked inspected, that every landmark has an explicit status, that coordinates fall inside the image bounds, that occluded/not-applicable points have null coordinates, and that the inspection method, confidence and grip fields are well-formed.

It does **not** and cannot validate clothing fit, grips, or whether a hand-placed landmark is anatomically correct. Use the contact sheets for that.

If a portrait changes, the hash check fails. Re-inspect that image and update `inspection-notes.txt` before trusting its landmarks again.
