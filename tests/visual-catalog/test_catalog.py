"""Tests for tools/visual-catalog. Run from the repository root:

    python3 -m unittest discover -s tests/visual-catalog
"""
import copy
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("visual_catalog", REPO / "tools" / "visual-catalog" / "catalog.py")
vc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vc  # dataclasses need the module registered
SPEC.loader.exec_module(vc)


def fresh():
    return vc.load()


class CatalogDataTests(unittest.TestCase):
    def setUp(self):
        self.cat = fresh()
        self.res = vc.validate(self.cat)

    def test_catalog_validates(self):
        self.assertEqual(self.res.errors, [])

    def test_every_class_combo_row_has_a_recipe(self):
        self.assertEqual(len(self.cat.selections), len(self.cat.combos))
        for s in self.cat.selections:
            rid, chain = self.cat.resolve(s["visual"])
            self.assertIsNotNone(rid, f"{s['selectionId']}: {chain}")

    def test_expected_catalog_size(self):
        self.assertEqual(len(self.cat.combos), 270)
        self.assertEqual(len({c["comboName"] for c in self.cat.combos}), 171)

    def test_only_expected_warning(self):
        self.assertEqual(len(self.res.warnings), 1)
        self.assertIn("creature.warhorse", self.res.warnings[0])

    def test_tables_are_current(self):
        tables = vc.render_tables(self.cat)
        for name, text in tables.items():
            path = vc.TABLES_DIR / name
            self.assertTrue(path.exists(), name)
            self.assertEqual(path.read_text(encoding="utf-8"), text, f"{name} is stale; run catalog.py tables")


class SorrowKnightTests(unittest.TestCase):
    def setUp(self):
        raw = (REPO / "backend" / "data" / "class-combos.json").read_bytes()
        self.raw = raw
        self.rows = json.loads(raw.decode("utf-8-sig"))

    def row(self, ruleset, cls, sub):
        hits = [r for r in self.rows if (r["classRuleset"], r["className"], r["subclassName"]) == (ruleset, cls, sub)]
        self.assertEqual(len(hits), 1)
        return hits[0]

    def test_file_keeps_bom(self):
        self.assertTrue(self.raw.startswith(b"\xef\xbb\xbf"))

    def test_row_fields(self):
        sk = self.row("5.5E", "Fighter", "Sorrow Knight")
        self.assertEqual(sk["comboName"], "Sorrow Knight Fighter")
        self.assertEqual(sk["subclassSourceGroup"], "5.5e Expanded Rules")
        self.assertEqual(sk["sources"], ["Player's Handbook (2024)", "D&D Beyond Drops"])
        self.assertEqual(sk["spellcasterGrade"], "Spell-less")

    def test_uses_champion_baseline_ratings(self):
        sk = self.row("5.5E", "Fighter", "Sorrow Knight")
        champ = self.row("5.5E", "Fighter", "Champion")
        for k in ("combatRoles", "outOfCombatRoles", "combatRatings", "outOfCombatRatings"):
            self.assertEqual(sk[k], champ[k], k)

    def test_visible_in_latest_mode_and_not_5e_mode(self):
        """Mirror of getVisibleClassCombos() filters in frontend/app.js."""
        sk = self.row("5.5E", "Fighter", "Sorrow Knight")
        latest = sk["classRuleset"] != "5E" and sk["subclassSourceGroup"] != "Critical Role" and "Critical Role" not in sk["sources"]
        five_e = sk["classRuleset"] == "5E" or re.match(r"^5e ", sk["subclassSourceGroup"], re.I)
        self.assertTrue(latest)
        self.assertFalse(five_e)

    def test_reuses_fighter_armor_and_existing_weapon(self):
        cat = fresh()
        vc.validate(cat)
        sel = next(s for s in cat.selections if s["selectionId"] == "5.5E|Fighter|Sorrow Knight")
        recipe = cat.recipe_by_id[cat.resolve(sel["visual"])[0]]
        champion = cat.recipe_by_id["fighter.champion"]
        self.assertEqual(recipe["artisticDefaults"]["wardrobe"], champion["artisticDefaults"]["wardrobe"])
        self.assertTrue(set(recipe["artisticDefaults"]["props"]) <= set(champion["artisticDefaults"]["props"]))
        self.assertEqual(recipe["artisticDefaults"]["signatureLayer"], "sig.sorrow-knight-shroud")
        mist = cat.by_id["fx.shadowfell-mist"][1]
        self.assertEqual(mist["base"], "fxbase.wisps")  # recolor, not a new design


class ValidatorNegativeTests(unittest.TestCase):
    def mutate(self, fn):
        cat = fresh()
        fn(cat)
        return vc.validate(cat)

    def test_missing_component_reference(self):
        def fn(cat):
            cat.recipes[0]["artisticDefaults"]["props"] = ["prop.does-not-exist"]
        res = self.mutate(fn)
        self.assertTrue(any("missing component" in e for e in res.errors))

    def test_wrong_component_type(self):
        def fn(cat):
            cat.recipes[0]["artisticDefaults"]["wardrobe"] = "prop.longsword"
        res = self.mutate(fn)
        self.assertTrue(any("expected wardrobes" in e for e in res.errors))

    def test_alias_cycle_rejected(self):
        def fn(cat):
            cat.aliases.append({"id": "test.a", "target": "test.b", "reason": "x"})
            cat.aliases.append({"id": "test.b", "target": "test.a", "reason": "x"})
            cat.selections[0]["visual"] = "test.a"
        res = self.mutate(fn)
        self.assertTrue(any("alias cycle" in e for e in res.errors))

    def test_alias_to_missing_target(self):
        def fn(cat):
            cat.aliases.append({"id": "test.orphan", "target": "test.nowhere", "reason": "x"})
        res = self.mutate(fn)
        self.assertTrue(any("does not exist" in e for e in res.errors))

    def test_duplicate_id_rejected(self):
        def fn(cat):
            cat.recipes.append(copy.deepcopy(cat.recipes[0]))
        res = self.mutate(fn)
        self.assertTrue(any("duplicate id" in e for e in res.errors))

    def test_invalid_id_rejected(self):
        def fn(cat):
            cat.components["props"].append({"id": "Prop Bad", "kind": "melee", "hands": 1})
        res = self.mutate(fn)
        self.assertTrue(any("invalid id" in e for e in res.errors))

    def test_uncovered_combo_row(self):
        def fn(cat):
            cat.combos = cat.combos + [dict(cat.combos[0], subclassName="Imaginary Path")]
        res = self.mutate(fn)
        self.assertTrue(any("no visual selection" in e for e in res.errors))

    def test_monk_in_armor_rejected(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "monk.shadow")["artisticDefaults"]["wardrobe"] = "wardrobe.light-leather"
        res = self.mutate(fn)
        self.assertTrue(any("monk-unarmored" in e or "armor training" in e for e in res.errors))

    def test_2014_druid_metal_rejected(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "druid.land")["artisticDefaults"]["wardrobe"] = "wardrobe.medium-breastplate"
        res = self.mutate(fn)
        self.assertTrue(any("selection 5E|Druid|Circle of the Land" in e and "druid-no-metal" in e for e in res.errors))
        # 2024 Druid has no metal rule, but still lacks medium armor without Warden.
        self.assertTrue(any("5.5E|Druid|Circle of the Land" in e and "armor training" in e for e in res.errors))

    def test_barbarian_heavy_armor_rejected(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "barbarian.berserker")["artisticDefaults"]["wardrobe"] = "wardrobe.heavy-plate"
        res = self.mutate(fn)
        self.assertTrue(any("rage-heavy-armor" in e for e in res.errors))

    def test_bladesinger_shield_rejected(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "wizard.bladesinging")["artisticDefaults"]["props"] = ["prop.rapier", "prop.shield-metal"]
        res = self.mutate(fn)
        self.assertTrue(any("bladesong" in e for e in res.errors))

    def test_cleric_heavy_needs_protector_assumption(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "cleric.war")["ruleAssumptions"] = []
        res = self.mutate(fn)
        self.assertTrue(any("5.5E|Cleric|War Domain" in e and "heavy" in e for e in res.errors))
        self.assertFalse(any("selection 5E|Cleric|War Domain:" in e for e in res.errors))  # 2014 War grants heavy

    def test_pose_requires_matching_props(self):
        def fn(cat):
            next(r for r in cat.recipes if r["id"] == "rogue.scout")["artisticDefaults"]["props"] = ["prop.rapier"]
        res = self.mutate(fn)
        self.assertTrue(any("bow-aiming needs a ranged prop" in e for e in res.errors))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.cat = fresh()
        vc.validate(self.cat)

    def test_dependency_counts_sum(self):
        dep = vc.dependency_report(self.cat)
        self.assertEqual(sum(r["selections"] for r in dep["wardrobes"]), 270)
        self.assertEqual(sum(r["selections"] for r in dep["poses"]), 270)

    def test_estimate_separates_counts(self):
        est = vc.estimate(self.cat, retry_factor=0.5)
        self.assertIn("uniqueDesigns", est)
        self.assertIn("deterministic", est)
        jobs = est["generationJobs"]
        self.assertGreater(jobs["withRetries"]["lower"], jobs["minimumJobsBeforeRetries"]["lower"])
        self.assertGreaterEqual(est["fittedExports"]["totalUpper"], est["fittedExports"]["totalLower"])

    def test_alias_groups_cover_all_selections(self):
        groups = vc.alias_groups(self.cat)
        self.assertEqual(sum(len(v) for v in groups.values()), 270)
        self.assertEqual(set(groups), {r["id"] for r in self.cat.recipes})


if __name__ == "__main__":
    unittest.main()
