#!/usr/bin/env python3
"""Offline validator and dependency report for the class visual-recipe catalog.

Standard library only. Usage (from the repository root):

    python3 tools/visual-catalog/catalog.py validate
    python3 tools/visual-catalog/catalog.py report
    python3 tools/visual-catalog/catalog.py estimate
    python3 tools/visual-catalog/catalog.py tables [--check]

What this checks: references, IDs, aliases, coverage of every class-combo row,
pose/hand consistency, and catalogued rules constraints (armor training,
Monk/Rage/Bladesong/2014-Druid limits). What it does NOT check: whether a
painted layer actually fits a body, or whether a grip looks right. Those need
visual review of the exported PNGs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_DIR = HERE / "data"
TABLES_DIR = HERE / "tables"
COMBOS_PATH = REPO_ROOT / "backend" / "data" / "class-combos.json"

ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")
CONFIDENCE = {"high", "medium", "low", "unverified"}
ARMOR_ORDER = ["light", "medium", "heavy"]
GRANTABLE = set(ARMOR_ORDER) | {"shields"}

# component collection -> (allowed id prefixes, recipe field)
COMPONENT_TYPES = {
    "wardrobes": ("wardrobe",),
    "poses": ("pose",),
    "props": ("prop",),
    "accessoryKits": ("kit",),
    "effectBases": ("fxbase",),
    "effects": ("fx",),
    "signatureLayers": ("sig",),
    "creatures": ("creature", "transform"),
}
WEAPON_KINDS = {"melee", "ranged", "firearm"}


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class Catalog:
    components: dict
    recipes: list
    aliases: list
    selections: list
    class_rules: dict
    sources: dict
    body_families: dict
    combos: list

    # derived indexes, filled by index()
    by_id: dict = field(default_factory=dict)          # component id -> (collection, obj)
    recipe_by_id: dict = field(default_factory=dict)
    alias_by_id: dict = field(default_factory=dict)

    def index(self, result: Result) -> None:
        seen: dict[str, str] = {}

        def claim(i: str, where: str) -> bool:
            if not isinstance(i, str) or not ID_RE.match(i):
                result.errors.append(f"{where}: invalid id {i!r}")
                return False
            if i in seen:
                result.errors.append(f"duplicate id {i!r} in {where} (already used in {seen[i]})")
                return False
            seen[i] = where
            return True

        for coll, prefixes in COMPONENT_TYPES.items():
            for obj in self.components.get(coll, []):
                i = obj.get("id")
                if claim(i, coll):
                    if i.split(".", 1)[0] not in prefixes:
                        result.errors.append(f"{coll}: id {i!r} must start with one of {prefixes}")
                    self.by_id[i] = (coll, obj)
        for r in self.recipes:
            if claim(r.get("id"), "recipes"):
                self.recipe_by_id[r["id"]] = r
        for a in self.aliases:
            if claim(a.get("id"), "aliases"):
                self.alias_by_id[a["id"]] = a

    def resolve(self, visual_id: str) -> tuple[str | None, list[str]]:
        """Follow aliases to a recipe id. Returns (recipe_id or None, chain)."""
        chain = [visual_id]
        current = visual_id
        while current in self.alias_by_id:
            current = self.alias_by_id[current]["target"]
            if current in chain:
                chain.append(current)
                return None, chain
            chain.append(current)
        return (current if current in self.recipe_by_id else None), chain


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load(data_dir: Path = DATA_DIR, combos_path: Path = COMBOS_PATH) -> Catalog:
    recipes = _read_json(data_dir / "recipes.json")
    return Catalog(
        components=_read_json(data_dir / "components.json"),
        recipes=recipes["recipes"],
        aliases=recipes.get("aliases", []),
        selections=_read_json(data_dir / "selections.json")["selections"],
        class_rules=_read_json(data_dir / "class-rules.json")["classes"],
        sources=_read_json(data_dir / "sources.json")["sources"],
        body_families=_read_json(data_dir / "body-families.json"),
        combos=_read_json(combos_path),
    )


def selection_key(row: dict) -> str:
    return "|".join((row["classRuleset"], row["className"], row["subclassName"]))


def recipe_components(recipe: dict) -> list[tuple[str, str]]:
    """(field, component id) pairs referenced by a recipe's artistic defaults."""
    d = recipe.get("artisticDefaults", {})
    refs = [("wardrobe", d.get("wardrobe")), ("pose", d.get("pose")), ("accessoryKit", d.get("accessoryKit"))]
    refs += [("props", p) for p in d.get("props", [])]
    refs += [("effects", e) for e in d.get("effects", [])]
    if d.get("signatureLayer"):
        refs.append(("signatureLayer", d["signatureLayer"]))
    if d.get("companionOrTransformation"):
        refs.append(("companionOrTransformation", d["companionOrTransformation"]))
    return refs


FIELD_COLLECTION = {
    "wardrobe": "wardrobes", "pose": "poses", "accessoryKit": "accessoryKits", "props": "props",
    "effects": "effects", "signatureLayer": "signatureLayers", "companionOrTransformation": "creatures",
}


# ------------------------------------------------------------------ validation
def validate(cat: Catalog) -> Result:
    res = Result()
    cat.index(res)
    _check_effects(cat, res)
    _check_recipes(cat, res)
    _check_aliases(cat, res)
    _check_selections(cat, res)
    _check_rules(cat, res)
    _check_creature_flags(cat, res)
    _check_unused(cat, res)
    return res


def _check_effects(cat: Catalog, res: Result) -> None:
    for e in cat.components.get("effects", []):
        base = cat.by_id.get(e.get("base"))
        if not base or base[0] != "effectBases":
            res.errors.append(f"effect {e.get('id')}: unknown base {e.get('base')!r}")


def _check_recipes(cat: Catalog, res: Result) -> None:
    for r in cat.recipes:
        rid = r.get("id")
        if r.get("confidence") not in CONFIDENCE:
            res.errors.append(f"recipe {rid}: confidence must be one of {sorted(CONFIDENCE)}")
        for fld, cid in recipe_components(r):
            if cid is None:
                res.errors.append(f"recipe {rid}: missing {fld}")
                continue
            hit = cat.by_id.get(cid)
            if not hit:
                res.errors.append(f"recipe {rid}: {fld} references missing component {cid!r}")
            elif hit[0] != FIELD_COLLECTION[fld]:
                res.errors.append(f"recipe {rid}: {fld} {cid!r} is a {hit[0]} entry, expected {FIELD_COLLECTION[fld]}")
        _check_pose(cat, r, res)


def _check_pose(cat: Catalog, r: dict, res: Result) -> None:
    d = r.get("artisticDefaults", {})
    pose = d.get("pose")
    props = [cat.by_id[p][1] for p in d.get("props", []) if p in cat.by_id and cat.by_id[p][0] == "props"]
    rid = r.get("id")
    hands = sum(p["hands"] for p in props)
    if hands > 2:
        res.errors.append(f"recipe {rid}: props need {hands} hands")
    kinds = [p["kind"] for p in props]
    two_handed = [p for p in props if p["hands"] == 2]
    if pose == "pose.two-handed-ready" and not any(p["kind"] == "melee" for p in two_handed):
        res.errors.append(f"recipe {rid}: two-handed-ready needs a two-handed melee prop")
    if pose == "pose.bow-aiming" and not any(p["kind"] == "ranged" for p in props):
        res.errors.append(f"recipe {rid}: bow-aiming needs a ranged prop")
    if pose == "pose.instrument-playing" and "instrument" not in kinds:
        res.errors.append(f"recipe {rid}: instrument-playing needs an instrument prop")
    if pose == "pose.unarmed-guard" and props:
        res.errors.append(f"recipe {rid}: unarmed-guard must have empty hands")
    if pose == "pose.one-handed-ready" and not any(p["kind"] in WEAPON_KINDS and p["hands"] == 1 for p in props):
        res.errors.append(f"recipe {rid}: one-handed-ready needs a one-handed weapon")
    if pose in ("pose.one-handed-ready", "pose.casting") and two_handed:
        res.errors.append(f"recipe {rid}: {pose} cannot hold a two-handed prop")
    if pose != "pose.instrument-playing" and "instrument" in kinds:
        res.errors.append(f"recipe {rid}: instrument held outside instrument-playing pose")


def _check_aliases(cat: Catalog, res: Result) -> None:
    for a in cat.aliases:
        aid = a.get("id")
        target = a.get("target")
        if target not in cat.alias_by_id and target not in cat.recipe_by_id:
            res.errors.append(f"alias {aid}: target {target!r} does not exist")
            continue
        recipe, chain = cat.resolve(aid)
        if recipe is None and chain[-1] in chain[:-1]:
            res.errors.append(f"alias cycle: {' -> '.join(chain)}")
        if not a.get("reason"):
            res.warnings.append(f"alias {aid}: no reason recorded")


def _check_selections(cat: Catalog, res: Result) -> None:
    combo_keys = [selection_key(c) for c in cat.combos]
    if len(set(combo_keys)) != len(combo_keys):
        res.errors.append("class-combos.json has duplicate ruleset/class/subclass rows")
    sel_ids = [s.get("selectionId") for s in cat.selections]
    missing = sorted(set(combo_keys) - set(sel_ids))
    extra = sorted(set(sel_ids) - set(combo_keys))
    for m in missing:
        res.errors.append(f"class-combo row has no visual selection: {m}")
    for x in extra:
        res.errors.append(f"selection not present in class-combos.json: {x}")
    if len(set(sel_ids)) != len(sel_ids):
        res.errors.append("duplicate selectionId in selections.json")

    combos_by_key = {selection_key(c): c for c in cat.combos}
    for s in cat.selections:
        sid = s.get("selectionId")
        recipe_id, chain = cat.resolve(s.get("visual", ""))
        if recipe_id is None:
            res.errors.append(f"selection {sid}: visual {s.get('visual')!r} does not resolve to a recipe ({' -> '.join(chain)})")
            continue
        recipe = cat.recipe_by_id[recipe_id]
        if recipe.get("className") != s.get("className"):
            res.errors.append(f"selection {sid}: recipe {recipe_id} is for {recipe.get('className')}")
        row = combos_by_key.get(sid)
        if row and row.get("comboName") != s.get("comboName"):
            res.errors.append(f"selection {sid}: comboName differs from class-combos.json")
        for src in s.get("sources", []):
            if src not in cat.sources:
                res.errors.append(f"selection {sid}: unknown source id {src!r}")
        if row:
            titles = [cat.sources.get(x, {}).get("title") for x in s.get("sources", [])]
            if titles != row.get("sources"):
                res.errors.append(f"selection {sid}: sources {titles} differ from class-combos.json {row.get('sources')}")
        rules = s.get("rules", {})
        for g in rules.get("armorGrants", []):
            if g not in GRANTABLE:
                res.errors.append(f"selection {sid}: unknown armor grant {g!r}")
        for fact in rules.get("facts", []) + rules.get("featureLevels", []):
            if fact.get("source") not in cat.sources:
                res.errors.append(f"selection {sid}: fact cites unknown source {fact.get('source')!r}")
        if s.get("confidence") not in CONFIDENCE:
            res.errors.append(f"selection {sid}: bad confidence {s.get('confidence')!r}")


def effective_training(cat: Catalog, selection: dict, recipe: dict) -> tuple[set, bool, list[str], list[str]]:
    """Armor categories, shield training, options applied, options available."""
    rules = cat.class_rules.get(f"{selection['classRuleset']}:{selection['className']}", {})
    armor = set(rules.get("armorTraining", []))
    shields = bool(rules.get("shields"))
    grants = selection.get("rules", {}).get("armorGrants", [])
    armor |= {g for g in grants if g in ARMOR_ORDER}
    shields = shields or "shields" in grants
    applied, available = [], []
    for opt in rules.get("options", []):
        available.append(opt["id"])
        if opt["id"] in recipe.get("ruleAssumptions", []):
            applied.append(opt["id"])
            armor |= {g for g in opt.get("grants", []) if g in ARMOR_ORDER}
            shields = shields or "shields" in opt.get("grants", [])
    return armor, shields, applied, available


def _check_rules(cat: Catalog, res: Result) -> None:
    all_options = {o["id"] for r in cat.class_rules.values() for o in r.get("options", [])}
    for r in cat.recipes:
        for a in r.get("ruleAssumptions", []):
            if a not in all_options:
                res.errors.append(f"recipe {r['id']}: unknown rule assumption {a!r}")

    for s in cat.selections:
        sid = s["selectionId"]
        recipe_id, _ = cat.resolve(s.get("visual", ""))
        if not recipe_id:
            continue
        recipe = cat.recipe_by_id[recipe_id]
        key = f"{s['classRuleset']}:{s['className']}"
        if key not in cat.class_rules:
            res.errors.append(f"selection {sid}: no class rules for {key}")
            continue
        d = recipe["artisticDefaults"]
        wardrobe = cat.by_id.get(d["wardrobe"], (None, {}))[1]
        props = [cat.by_id[p][1] for p in d.get("props", []) if p in cat.by_id]
        shields_held = [p for p in props if p.get("kind") == "shield"]
        armor, shield_ok, applied, available = effective_training(cat, s, recipe)
        cat_needed = wardrobe.get("armorCategory", "none")

        if cat_needed != "none" and cat_needed not in armor:
            res.errors.append(f"selection {sid}: {d['wardrobe']} needs {cat_needed} armor training (has {sorted(armor) or 'none'})")
        if shields_held and not shield_ok:
            res.errors.append(f"selection {sid}: holds a shield without shield training")
        if applied:
            res.info.append(f"selection {sid}: relies on class option {', '.join(applied)}")

        restrictions = list(cat.class_rules[key].get("restrictions", [])) + list(s.get("rules", {}).get("restrictions", []))
        for rule in restrictions:
            _apply_restriction(rule, sid, wardrobe, props, shields_held, res)


def _apply_restriction(rule: dict, sid: str, wardrobe: dict, props: list, shields_held: list, res: Result) -> None:
    kind = rule.get("kind")
    sink = {"error": res.errors, "warning": res.warnings}.get(rule.get("severity"), res.info)
    cat_ = wardrobe.get("armorCategory", "none")
    if kind == "requires-no-armor-no-shield":
        if cat_ != "none" or shields_held:
            sink.append(f"selection {sid}: violates {rule['id']} ({rule['text']})")
    elif kind == "forbid-armor-category":
        if cat_ == rule.get("category"):
            sink.append(f"selection {sid}: violates {rule['id']} ({rule['text']})")
    elif kind == "forbid-metal":
        if wardrobe.get("metal") or any(p.get("metal") for p in shields_held):
            sink.append(f"selection {sid}: violates {rule['id']} ({rule['text']})")
    elif kind == "bladesong":
        two_handed_weapon = any(p.get("hands") == 2 and p.get("kind") in WEAPON_KINDS for p in props)
        if cat_ in ("medium", "heavy") or shields_held or two_handed_weapon:
            sink.append(f"selection {sid}: violates {rule['id']} ({rule['text']})")
    elif kind == "species-restriction":
        res.info.append(f"selection {sid}: {rule['id']}: {rule['text']}")
    else:
        res.errors.append(f"selection {sid}: unknown restriction kind {kind!r}")


def _check_creature_flags(cat: Catalog, res: Result) -> None:
    families = set(cat.body_families["baseline"]["families"])
    users = _component_users(cat)
    for c in cat.components.get("creatures", []):
        for fam in c.get("incompatibleBodyFamilies", []):
            if fam not in families:
                res.errors.append(f"creature {c['id']}: unknown body family {fam!r}")
            elif users.get(c["id"]):
                res.warnings.append(
                    f"{c['id']} is used by {len(users[c['id']])} selection(s) and is incompatible with "
                    f"{fam}: {c.get('incompatibilityNote', '')}")


def _check_unused(cat: Catalog, res: Result) -> None:
    users = _component_users(cat)
    used_bases = {cat.by_id[e][1]["base"] for e in users if e in cat.by_id and cat.by_id[e][0] == "effects"}
    for cid, (coll, _) in cat.by_id.items():
        if coll == "effectBases":
            if cid not in used_bases:
                res.warnings.append(f"unused effect base {cid}")
        elif coll != "poses" and not users.get(cid):
            res.warnings.append(f"unused component {cid}")
    used_aliases = {s.get("visual") for s in cat.selections}
    for a in cat.aliases:
        if a["id"] not in used_aliases and not any(b["target"] == a["id"] for b in cat.aliases):
            res.warnings.append(f"alias {a['id']} is not used by any selection")
    for r in cat.recipes:
        if not any(cat.resolve(s.get("visual", ""))[0] == r["id"] for s in cat.selections):
            res.warnings.append(f"recipe {r['id']} is not reachable from any selection")


# ------------------------------------------------------------------ reporting
def _component_users(cat: Catalog) -> dict[str, list[str]]:
    users: dict[str, list[str]] = defaultdict(list)
    for s in cat.selections:
        recipe_id, _ = cat.resolve(s.get("visual", ""))
        if not recipe_id:
            continue
        for _, cid in recipe_components(cat.recipe_by_id[recipe_id]):
            if cid and s["selectionId"] not in users[cid]:
                users[cid].append(s["selectionId"])
    return users


def dependency_report(cat: Catalog) -> dict:
    users = _component_users(cat)
    recipe_users: dict[str, set] = defaultdict(set)
    for s in cat.selections:
        rid, _ = cat.resolve(s.get("visual", ""))
        if not rid:
            continue
        for _, cid in recipe_components(cat.recipe_by_id[rid]):
            recipe_users[cid].add(rid)
    out = {}
    for coll in COMPONENT_TYPES:
        rows = []
        for obj in cat.components.get(coll, []):
            cid = obj["id"]
            if coll == "effectBases":
                derived = [e["id"] for e in cat.components["effects"] if e["base"] == cid]
                sel = sorted({u for e in derived for u in users.get(e, [])})
                rows.append({"id": cid, "selections": len(sel), "recipes": len({r for e in derived for r in recipe_users.get(e, set())}),
                             "derivedEffects": derived})
            else:
                rows.append({"id": cid, "selections": len(users.get(cid, [])), "recipes": len(recipe_users.get(cid, set())),
                             "selectionIds": sorted(users.get(cid, []))})
        out[coll] = sorted(rows, key=lambda r: (-r["selections"], r["id"]))
    return out


def alias_groups(cat: Catalog) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for s in cat.selections:
        rid, _ = cat.resolve(s.get("visual", ""))
        if rid:
            groups[rid].append(s["selectionId"])
    return dict(groups)


def evidence_summary(cat: Catalog) -> dict:
    facts = defaultdict(int)
    levels = defaultdict(int)
    for s in cat.selections:
        for f in s["rules"].get("facts", []):
            facts[f["confidence"]] += 1
        for f in s["rules"].get("featureLevels", []):
            levels[f["confidence"]] += 1
    class_facts = defaultdict(int)
    for r in cat.class_rules.values():
        class_facts[r["confidence"]] += 1
    return {
        "verifiedFacts": {
            "note": "Rules facts recorded from published sources. None were re-read against source text in this session.",
            "classArmorRulesByConfidence": dict(class_facts),
            "selectionFactsByConfidence": dict(facts),
            "featureLevelsByConfidence": dict(levels),
        },
        "artisticDefaults": {
            "recipes": len(cat.recipes),
            "recipesByConfidence": _count(r["confidence"] for r in cat.recipes),
            "recipesWithRuleAssumptions": sorted(r["id"] for r in cat.recipes if r.get("ruleAssumptions")),
        },
        "unresolved": {
            "selections": sorted(s["selectionId"] for s in cat.selections if s.get("unresolved")),
            "recipes": sorted(r["id"] for r in cat.recipes if r.get("unresolved")),
            "selectionsByConfidence": _count(s["confidence"] for s in cat.selections),
        },
    }


def _count(values) -> dict:
    out: dict = defaultdict(int)
    for v in values:
        out[v] += 1
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ estimate
def estimate(cat: Catalog, retry_factor: float | None = None) -> dict:
    """Export requirements from reachable recipe/component combinations.

    Only components reachable from at least one selection are counted, and
    each fitted component is multiplied by body families (not by species,
    presentation and pose).
    """
    users = _component_users(cat)
    reachable = {cid for cid, sel in users.items() if sel}
    bf = cat.body_families
    families = list(bf["baseline"]["families"])
    policy = bf["fitPolicy"]
    cuts_lo, cuts_hi = policy["cutsPerFamily"]["lower"], policy["cutsPerFamily"]["upper"]
    quad = "quadrupedal-humanoid"
    barding = len(policy["quadrupedBardingVariants"])
    species_total = sum(len(v) for v in bf["baseline"]["families"].values())

    def fitted_body(armor_category: str | None) -> tuple[int, int]:
        lo = len(families) * cuts_lo
        hi = len(families) * cuts_hi
        if armor_category in ARMOR_ORDER:  # extra barding export for the second quadruped type
            lo += (barding - 1) * cuts_lo
            hi += (barding - 1) * cuts_hi
        return lo, hi

    unique = defaultdict(int)
    fitted_lo = defaultdict(int)
    fitted_hi = defaultdict(int)
    deterministic = defaultdict(int)
    notes = []

    for w in cat.components["wardrobes"]:
        if w["id"] not in reachable:
            continue
        if w["id"] == "wardrobe.travel-clothes" and policy.get("travelClothesReusesBasePortrait"):
            notes.append("Travel clothes counted as 0 exports: current portraits already wear travel clothes.")
            continue
        unique["wardrobes"] += 1
        lo, hi = fitted_body(w["armorCategory"])
        fitted_lo["wardrobes"] += lo
        fitted_hi["wardrobes"] += hi
    for coll in ("accessoryKits", "signatureLayers"):
        for k in cat.components[coll]:
            if k["id"] in reachable:
                unique[coll] += 1
                lo, hi = fitted_body(None)
                fitted_lo[coll] += lo
                fitted_hi[coll] += hi

    prop_pose = set()
    for r in cat.recipes:
        if not any(cat.resolve(s["visual"])[0] == r["id"] for s in cat.selections):
            continue
        for p in r["artisticDefaults"]["props"]:
            prop_pose.add((p, r["artisticDefaults"]["pose"]))
    unique["props"] = len({p for p, _ in prop_pose})
    fitted_lo["props"] = fitted_hi["props"] = len(prop_pose)
    deterministic["prop scale-to-family"] = len(prop_pose) * len(families)
    notes.append("Props: one painted export per prop/pose grip pair; resizing per body family is deterministic.")

    used_effects = [e for e in cat.components["effects"] if e["id"] in reachable]
    bases = {e["base"] for e in used_effects}
    base_fit = {b["id"]: b["fit"] for b in cat.components["effectBases"]}
    unique["effect bases"] = len(bases)
    fitted_lo["effect bases"] = fitted_hi["effect bases"] = sum(1 for b in bases if base_fit[b] in ("free", "pose-anchor"))
    deterministic["effect recolors"] = len(used_effects)
    deterministic["mask-derived effects (runtime)"] = sum(1 for e in used_effects if base_fit[e["base"]] == "mask-derived")

    for c in cat.components["creatures"]:
        if c["id"] not in reachable:
            continue
        kind = c["kind"]
        if kind == "shared-creature":
            unique["shared creatures"] += 1
            fitted_lo["shared creatures"] += 1
            fitted_hi["shared creatures"] += 1
        elif kind == "overlay-fitted":
            unique["fitted overlays"] += 1
            lo, hi = fitted_body(None)
            fitted_lo["fitted overlays"] += lo
            fitted_hi["fitted overlays"] += hi
        elif kind == "composition":
            deterministic["transform compositions"] += 1
        elif kind == "hybrid-character":
            unique["hybrid transformations"] += 1
            fitted_lo["hybrid transformations"] += species_total
            fitted_hi["hybrid transformations"] += species_total * 3
            notes.append(f"{c['id']} is character-specific: up to one repaint per species x presentation. Consider an overlay approach.")

    total_unique = sum(unique.values())
    total_lo = sum(fitted_lo.values())
    total_hi = sum(fitted_hi.values())
    jobs = {
        "minimumJobsBeforeRetries": {"lower": total_unique + total_lo, "upper": total_unique + total_hi},
        "note": "One generation job per unique painted master plus one per fitted export. Retries are extra and are not exports.",
    }
    if retry_factor is not None:
        jobs["withRetries"] = {"retryFactor": retry_factor,
                               "lower": round((total_unique + total_lo) * (1 + retry_factor)),
                               "upper": round((total_unique + total_hi) * (1 + retry_factor))}
    return {
        "assumptions": {
            "bodyFamilies": families,
            "cutsPerFamily": policy["cutsPerFamily"],
            "quadrupedBardingVariants": policy["quadrupedBardingVariants"],
            "speciesCount": species_total,
            "speciesCountNote": "Includes Custom Lineage (Human exemplar).",
            "notMultipliedBy": ["species (except hybrid transformations)", "pose (except prop grips)", "presentation beyond cutsPerFamily"],
            "baseCharacterPoses": "Posed base bodies (species x presentation x pose) belong to the rendering workstream and are not counted here.",
        },
        "uniqueDesigns": dict(unique),
        "fittedExports": {"lower": dict(fitted_lo), "upper": dict(fitted_hi), "totalLower": total_lo, "totalUpper": total_hi},
        "deterministic": dict(deterministic),
        "generationJobs": jobs,
        "notes": notes,
        "disclaimer": "Metadata estimate only; it does not validate clothing fit or grips.",
    }


# ------------------------------------------------------------------ tables
def _md_table(headers: list[str], rows: list[list]) -> str:
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def _short(cid: str | None) -> str:
    return cid.split(".", 1)[1] if cid else ""


def render_tables(cat: Catalog) -> dict[str, str]:
    header = "<!-- Generated by tools/visual-catalog/catalog.py tables. Do not edit by hand. -->\n\n"
    groups = alias_groups(cat)
    recipe_rows = []
    for r in sorted(cat.recipes, key=lambda r: r["id"]):
        d = r["artisticDefaults"]
        recipe_rows.append([
            r["id"], len(groups.get(r["id"], [])), _short(d["wardrobe"]), _short(d["pose"]),
            ", ".join(_short(p) for p in d["props"]), _short(d["accessoryKit"]),
            ", ".join(_short(e) for e in d["effects"]), _short(d.get("signatureLayer")),
            d.get("companionOrTransformation") or "", "; ".join(r["subclassCues"]), r["confidence"],
            "; ".join(r["ruleAssumptions"]),
        ])
    recipes_md = header + "# Visual recipes\n\nArtistic defaults only; rules facts live in `selections.md`.\n\n" + _md_table(
        ["Recipe", "Selections", "Wardrobe", "Pose", "Props", "Kit", "Effects", "Signature", "Companion / form",
         "Subclass cues", "Confidence", "Rule assumptions"], recipe_rows)

    sel_rows = []
    for s in cat.selections:
        rid, chain = cat.resolve(s["visual"])
        rules = s["rules"]
        facts = "; ".join(f"{f['text']} [{f['source']}, {f['confidence']}]" for f in rules["facts"])
        levels = "; ".join(f"L{f['level']} {f['feature']}" for f in rules["featureLevels"])
        restr = "; ".join(x["id"] for x in rules["restrictions"])
        sel_rows.append([s["selectionId"], s["comboName"], ", ".join(s["sources"]),
                         " -> ".join(chain), ", ".join(rules["armorGrants"]), restr, levels, facts,
                         s["confidence"], "; ".join(s["unresolved"])])
    selections_md = header + "# Selections\n\nOne row per `backend/data/class-combos.json` row.\n\n" + _md_table(
        ["Selection", "Combo", "Sources", "Visual (alias chain)", "Armor grants", "Restrictions", "Feature levels",
         "Rules facts", "Confidence", "Unresolved"], sel_rows)

    alias_rows = []
    alias_ids = {a["id"] for a in cat.aliases}
    for rid, sels in sorted(groups.items()):
        visuals = sorted({s["visual"] for s in cat.selections if cat.resolve(s["visual"])[0] == rid})
        if len(sels) > 1 or any(v in alias_ids for v in visuals):
            alias_rows.append([rid, ", ".join(v for v in visuals if v in alias_ids), "<br>".join(sels)])
    reasons = [[a["id"], a["target"], a["reason"]] for a in cat.aliases]
    aliases_md = header + "# Alias groups\n\nSelections sharing one visual recipe. Rules identities stay separate.\n\n" + _md_table(
        ["Recipe", "Explicit aliases", "Selections"], alias_rows) + "\n## Alias reasons\n\n" + _md_table(
        ["Alias", "Target", "Reason"], reasons)

    dep = dependency_report(cat)
    parts = [header, "# Shared components and dependents\n"]
    for coll, rows in dep.items():
        parts.append(f"\n## {coll}\n\n")
        if coll == "effectBases":
            parts.append(_md_table(["Base", "Selections", "Recipes", "Derived effects (recolors)"],
                                   [[r["id"], r["selections"], r["recipes"], ", ".join(r["derivedEffects"])] for r in rows]))
        else:
            parts.append(_md_table(["Component", "Selections", "Recipes"], [[r["id"], r["selections"], r["recipes"]] for r in rows]))
    deps_md = "".join(parts)

    est = estimate(cat)
    est_md = header + "# Export estimate\n\n" + est["disclaimer"] + "\n\n```json\n" + json.dumps(est, indent=2) + "\n```\n"
    ev_md = header + "# Evidence summary\n\n```json\n" + json.dumps(evidence_summary(cat), indent=2) + "\n```\n"
    return {"recipes.md": recipes_md, "selections.md": selections_md, "aliases.md": aliases_md,
            "dependencies.md": deps_md, "estimate.md": est_md, "evidence.md": ev_md}


# ------------------------------------------------------------------ CLI
def _print_result(res: Result, verbose: bool) -> None:
    for e in res.errors:
        print(f"ERROR   {e}")
    for w in res.warnings:
        print(f"WARNING {w}")
    if verbose:
        for i in res.info:
            print(f"INFO    {i}")
    print(f"{len(res.errors)} error(s), {len(res.warnings)} warning(s), {len(res.info)} info")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("-v", "--verbose", action="store_true", help="also print info lines")
    sub.add_parser("report")
    e = sub.add_parser("estimate")
    e.add_argument("--retry-factor", type=float, default=None, help="extra attempts per job, e.g. 0.5")
    t = sub.add_parser("tables")
    t.add_argument("--check", action="store_true", help="fail if committed tables are stale")
    args = ap.parse_args(argv)

    cat = load()
    res = validate(cat)
    if args.cmd == "validate":
        _print_result(res, args.verbose)
        return 0 if res.ok else 1
    if not res.ok:
        _print_result(res, False)
        return 1
    if args.cmd == "report":
        counts = {coll: len(cat.components.get(coll, [])) for coll in COMPONENT_TYPES}
        groups = alias_groups(cat)
        print(json.dumps({
            "selections": len(cat.selections),
            "distinctComboNames": len({s["comboName"] for s in cat.selections}),
            "recipes": len(cat.recipes),
            "aliases": len(cat.aliases),
            "recipesSharedBySeveralSelections": sum(1 for g in groups.values() if len(g) > 1),
            "componentCounts": counts,
            "dependencies": {coll: [{k: r[k] for k in ("id", "selections", "recipes")} for r in rows]
                             for coll, rows in dependency_report(cat).items()},
            "evidence": evidence_summary(cat),
        }, indent=2))
        return 0
    if args.cmd == "estimate":
        print(json.dumps(estimate(cat, args.retry_factor), indent=2))
        return 0
    if args.cmd == "tables":
        tables = render_tables(cat)
        stale = []
        TABLES_DIR.mkdir(exist_ok=True)
        for name, text in tables.items():
            path = TABLES_DIR / name
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    stale.append(name)
            else:
                path.write_text(text, encoding="utf-8")
        if stale:
            print("stale tables: " + ", ".join(stale) + " (run: python3 tools/visual-catalog/catalog.py tables)")
            return 1
        print("tables up to date" if args.check else f"wrote {len(tables)} tables to {TABLES_DIR.relative_to(REPO_ROOT)}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
