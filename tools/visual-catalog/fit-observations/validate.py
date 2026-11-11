#!/usr/bin/env python3
"""Validate the fit-observation data files.

    python3 tools/visual-catalog/fit-observations/validate.py      # from repo root; exit 1 on errors

Checks:
  * source hashes, dimensions and paths match the files on disk
  * roster coverage: every group x presentation in species-groups.json has exactly one
    observation and one landmark set, with no extras; expected-but-missing species
    (e.g. Bariaur) appear only under "unavailable" and are not marked inspected
  * every landmark has an explicit status, coordinates lie inside the image bounds, and
    occluded / not-applicable / unlocated landmarks carry null coordinates (never invented values)
  * observations are marked inspected only with a stated method and confidence
  * hand records: gripCategory is one of the known values and cylindricalGrip is a boolean

What it does NOT check (cannot be automated from metadata):
  * whether any clothing, armour or prop layer actually fits a body
  * whether a hand can hold a prop, or whether a grip looks right
  * whether hand-placed landmarks are anatomically correct (use contact-sheets/ for review)
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRES = ["male", "female", "androgynous"]
STATUSES = {"visible", "uncertain", "occluded", "not-applicable", "uncertain-unlocated"}
NULL_STATUSES = {"occluded", "not-applicable", "uncertain-unlocated"}
GRIPS = {"empty", "hidden", "holding-non-cylindrical", "holding-non-prop", "cylindrical"}
CONFIDENCE = {"high", "medium", "low"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def main():
    errors, warnings = [], []
    err = errors.append
    roster = json.loads((ROOT / "backend/data/species-groups.json").read_text(encoding="utf-8"))
    obs_doc = json.loads((HERE / "observations.json").read_text(encoding="utf-8"))
    lm_doc = json.loads((HERE / "landmarks.json").read_text(encoding="utf-8"))
    expected = {(g["id"], p): g["imageVariants"][p] for g in roster["groups"] for p in PRES}
    roster_ids = {g["id"] for g in roster["groups"]}

    # ---- roster coverage
    for name, items in (("observations", obs_doc["observations"]), ("landmarks", lm_doc["images"])):
        keys = [(o["groupId"], o["presentation"]) for o in items]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            err(f"{name}: duplicate entries {sorted(dup)}")
        missing = set(expected) - set(keys)
        extra = set(keys) - set(expected)
        if missing:
            err(f"{name}: roster entries without data: {sorted(missing)}")
        if extra:
            err(f"{name}: entries not in roster (unreferenced images must not count as species): {sorted(extra)}")
    for doc in (obs_doc, lm_doc):
        for u in doc.get("unavailable", []):
            if u["groupId"] in roster_ids:
                err(f"{u['groupId']} is listed as unavailable but is present in the roster")
            if u.get("inspected"):
                err(f"{u['groupId']} is unavailable but marked inspected")

    # ---- sources
    hash_cache = {}
    for name, items in (("observations", obs_doc["observations"]), ("landmarks", lm_doc["images"])):
        for o in items:
            k = (o["groupId"], o["presentation"])
            src = o["source"]
            if k in expected:
                want = str(Path("frontend") / expected[k].lstrip("./"))
                if src["path"] != want:
                    err(f"{name} {k}: path {src['path']} != roster {want}")
            p = ROOT / src["path"]
            if not p.exists():
                err(f"{name} {k}: source missing {src['path']}")
                continue
            if src["path"] not in hash_cache:
                hash_cache[src["path"]] = sha256(p)
            if src["sha256"] != hash_cache[src["path"]]:
                err(f"{name} {k}: sha256 mismatch for {src['path']} (portrait changed since inspection; re-inspect before trusting landmarks)")
            if p.suffix == ".png":
                from PIL import Image
                with Image.open(p) as im:
                    if list(im.size) != [src["widthPx"], src["heightPx"]]:
                        err(f"{name} {k}: dimensions {im.size} != recorded {src['widthPx']}x{src['heightPx']}")

    # ---- inspection claims
    for o in obs_doc["observations"]:
        k = (o["groupId"], o["presentation"])
        ins = o.get("inspection") or {}
        if ins.get("inspected") is not True:
            warnings.append(f"{k}: not inspected")
        else:
            if not ins.get("method"):
                err(f"{k}: inspected without a method")
            if ins.get("confidence") not in CONFIDENCE:
                err(f"{k}: confidence must be one of {sorted(CONFIDENCE)}")
        if o.get("fitGroups"):
            for g in ("torso", "lowerBody", "sleeve", "hand", "footwear"):
                if not o["fitGroups"].get(g):
                    err(f"{k}: fitGroups.{g} missing")
            for c in ("horns", "ears", "wings", "tail", "shell", "hair", "beard"):
                if c not in (o.get("clearance") or {}):
                    err(f"{k}: clearance.{c} must be present (null = no concern)")

    # ---- landmarks
    for L in lm_doc["images"]:
        k = (L["groupId"], L["presentation"])
        w, h = L["source"]["widthPx"], L["source"]["heightPx"]
        if L.get("noFigure"):
            if L["landmarks"]:
                err(f"{k}: noFigure but landmarks present")
            continue
        if not L.get("inspected"):
            err(f"{k}: landmarks recorded for an image not marked inspected")
        required = [f"{n}.{s}" for n in ("shoulder", "elbow", "wrist", "hip", "knee", "foot")
                    for s in ("imageLeft", "imageRight")] + ["waist"]
        for r in required:
            if r not in L["landmarks"]:
                err(f"{k}: landmark {r} missing (record it as occluded/not-applicable instead of omitting it)")
        for name, v in L["landmarks"].items():
            st = v.get("status")
            if st not in STATUSES:
                err(f"{k} {name}: status {st!r} not explicit/known")
                continue
            x, y = v.get("x"), v.get("y")
            if st in NULL_STATUSES:
                if x is not None or y is not None:
                    err(f"{k} {name}: status {st} must have null coordinates")
                continue
            if v.get("kind") == "horizontal-line":
                if x is not None:
                    err(f"{k} {name}: line landmark must have x=null")
                if not isinstance(y, (int, float)) or not 0 <= y < h:
                    err(f"{k} {name}: y={y} out of bounds 0..{h - 1}")
                continue
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                err(f"{k} {name}: status {st} requires numeric x,y")
            elif not (0 <= x < w and 0 <= y < h):
                err(f"{k} {name}: ({x},{y}) outside image {w}x{h}")
            if name.startswith("wrist."):
                if v.get("gripCategory") not in GRIPS:
                    err(f"{k} {name}: gripCategory {v.get('gripCategory')!r} unknown")
                if not isinstance(v.get("cylindricalGrip"), bool):
                    err(f"{k} {name}: cylindricalGrip must be true/false")
                if v.get("cylindricalGrip") and v.get("gripCategory") != "cylindrical":
                    err(f"{k} {name}: cylindricalGrip true but gripCategory {v.get('gripCategory')}")
        for side in ("imageLeft", "imageRight"):  # hidden hands must not carry wrist coords pretending visibility
            v = L["landmarks"].get(f"wrist.{side}", {})
            if v.get("gripCategory") == "hidden" and v.get("status") == "visible" and v.get("handState", "").startswith(("in-pocket", "behind-back")):
                err(f"{k} wrist.{side}: hand is {v['handState']} but wrist is marked visible")

    n_obs = len(obs_doc["observations"])
    n_pts = sum(len(L["landmarks"]) for L in lm_doc["images"])
    for w_ in warnings:
        print("WARN ", w_)
    for e in errors:
        print("ERROR", e)
    print(f"checked {len(roster_ids)} roster groups x {len(PRES)} presentations = {len(expected)} entries; "
          f"{n_obs} observations, {n_pts} landmark records, {len(hash_cache)} unique source files hashed; "
          f"unavailable: {[u['groupId'] for u in obs_doc.get('unavailable', [])]}")
    print("NOTE  This validator checks data integrity only. It does not and cannot validate clothing fit or grips.")
    print("FAIL" if errors else "OK", f"({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
