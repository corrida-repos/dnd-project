#!/usr/bin/env python3
"""Build observations.json, landmarks.json and contact-sheets/ from the hand-written
inspection notes and annotations.

    python3 tools/visual-catalog/fit-observations/build.py           # from repo root
    python3 tools/visual-catalog/fit-observations/build.py --no-sheets

Inputs:  backend/data/species-groups.json (roster + image paths), frontend/assets/species/*,
         inspection-notes.txt, annotations.py
Outputs: written only inside this directory. Source portraits are opened read-only.

Landmarks come only from the notes, written while looking at each portrait on a
coordinate grid. The script never detects or invents points. Torso groups and
"differences from male" deltas are arithmetic on those hand-placed points.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import notes_parser  # noqa: E402
from annotations import SPECIES, EXPECTED_UNAVAILABLE, PRIORITY  # noqa: E402

ROSTER = ROOT / "backend/data/species-groups.json"
FRONTEND = ROOT / "frontend"
PRES = ["male", "female", "androgynous"]
LANDMARK_KEYS = [("sh", "shoulder"), ("el", "elbow"), ("wr", "wrist"), ("hip", "hip"), ("kn", "knee"), ("ft", "foot")]
PRECISION_PX = 30  # stated precision of hand-placed points (grid read at 0.4x, 100 px cells)
INSPECTION_METHOD = ("Viewed all three presentations side by side at 0.4x (about 410x614 px per image) "
                     "with a labelled 100 px grid in original coordinates; Centaur, Aarakocra, Fairy legs "
                     "and Warforged were also checked in 0.55-0.93x zoomed crops with a 50 px grid.")
ZOOMED = {"centaur", "aarakocra", "fairy", "warforged"}


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def dimensions(path):
    if path.suffix.lower() == ".svg":
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
        w = re.search(r'\bwidth="(\d+)', head)
        h = re.search(r'\bheight="(\d+)', head)
        return (int(w.group(1)) if w else None, int(h.group(1)) if h else None)
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# ---------------------------------------------------------------- hand states
def grip_category(state):
    s = state.lower()
    if s.startswith(("in-pocket", "behind-back", "tucked", "arms-crossed-hidden", "hidden")):
        return "hidden"
    if s.startswith("holding-own-forearm"):
        return "holding-non-prop"
    if s.startswith("holding-"):
        return "holding-non-cylindrical"
    return "empty"


# ---------------------------------------------------------------- metrics
def pt(d):
    return (d["x"], d["y"]) if d.get("x") is not None else None


def mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def metrics(rec):
    f = rec["fields"]
    shl, shr = pt(f["sh"]["imageLeft"]), pt(f["sh"]["imageRight"])
    hl, hr = pt(f["hip"]["imageLeft"]), pt(f["hip"]["imageRight"])
    m = {
        "shoulderWidthPx": abs(shr[0] - shl[0]) if shl and shr else None,
        "shoulderLineY": mean([shl and shl[1], shr and shr[1]]),
        "waistLineY": rec.get("waistY"),
        "hipWidthPx": abs(hr[0] - hl[0]) if hl and hr else None,
        "hipLineY": mean([hl and hl[1], hr and hr[1]]),
        "footLineY": mean([p and p[1] for p in (pt(f["ft"]["imageLeft"]), pt(f["ft"]["imageRight"]))]),
    }
    # arm length only for arms hanging empty (shoulder->elbow->wrist path)
    arms = []
    for side in ("imageLeft", "imageRight"):
        s, e, w = pt(f["sh"][side]), pt(f["el"][side]), pt(f["wr"][side])
        state = rec["hands"][side]
        if s and e and w and state.startswith("empty") and "extended" not in state and w[1] > e[1]:
            arms.append(math.dist(s, e) + math.dist(e, w))
    m["hangingArmLengthPx"] = round(sum(arms) / len(arms)) if arms else None
    m["torsoLengthPx"] = round(m["waistLineY"] - m["shoulderLineY"]) if m["waistLineY"] and m["shoulderLineY"] else None
    m["legLengthPx"] = round(m["footLineY"] - m["hipLineY"]) if m["footLineY"] and m["hipLineY"] else None
    return m


BORDER_PX = 20
HUMAN_MALE = {}  # filled in build(): baseline for placement offsets


def torso_derivation(m):
    w = m["shoulderWidthPx"]
    near = w is not None and min(abs(w - t) for t in (300, 360, 430)) < BORDER_PX
    return {
        "rule": "slim <300, standard 300-359, broad 360-429, heavy >=430 px between the two shoulder points",
        "borderline": bool(near),
        "caveat": "Shoulder points mark the outer shoulder/sleeve-cap silhouette as drawn, so puffy sleeves, "
                  "cloaks and plates widen it. A class within 20 px of a threshold can flip; check the "
                  "contact sheet before splitting artwork.",
    }


def placement(m):
    """Offsets relative to the Human male portrait: what a shared layer would need to move/scale by."""
    b = HUMAN_MALE
    out = {}
    for k in ("shoulderLineY", "waistLineY", "hipLineY", "footLineY"):
        out[f"{k}DeltaVsHumanMale"] = round(m[k] - b[k]) if m.get(k) is not None and b.get(k) is not None else None
    w, bw = m.get("shoulderWidthPx"), b.get("shoulderWidthPx")
    out["shoulderWidthScaleVsHumanMale"] = round(w / bw, 2) if w and bw else None
    tl, btl = m.get("torsoLengthPx"), b.get("torsoLengthPx")
    out["torsoLengthScaleVsHumanMale"] = round(tl / btl, 2) if tl and btl else None
    return out


def width_class(w):
    if w is None:
        return "unmeasured"
    return "slim" if w < 300 else "standard" if w < 360 else "broad" if w < 430 else "heavy"


def torso_group(back, m):
    return f"torso.{'plain' if back == 'none' else back}.{width_class(m['shoulderWidthPx'])}"


# ---------------------------------------------------------------- landmarks
def lm_entry(d, kind="point"):
    out = {"kind": kind, "status": d["status"], "x": d.get("x"), "y": d.get("y")}
    if d.get("note"):
        out["note"] = d["note"]
    return out


def landmarks_for(rec):
    f = rec["fields"]
    out = {}
    for key, name in LANDMARK_KEYS:
        for side in ("imageLeft", "imageRight"):
            d = lm_entry(f[key][side])
            if key == "wr":
                state = rec["hands"][side]
                d["handState"] = state
                d["gripCategory"] = grip_category(state)
                d["cylindricalGrip"] = False  # no portrait shows a cylindrical prop grip
            out[f"{name}.{side}"] = d
    out["waist"] = {"kind": "horizontal-line", "status": "visible" if rec.get("waistY") else "occluded",
                    "x": None, "y": rec.get("waistY"),
                    "note": "Waistline height read from belt/sash/bodice; x is not meaningful for a line. Clothing-dependent."}
    for name, val in rec["extra"].items():
        if name == "hooves":
            for h in val:
                out[f"hoof.{h['label']}"] = {"kind": "point", "status": h["status"], "x": h["x"], "y": h["y"]}
        else:
            for side in ("imageLeft", "imageRight"):
                out[f"{name}.{side}"] = lm_entry(val[side])
    return out


# ---------------------------------------------------------------- differences
def diff_from_male(gid, pres, m, male_m, groups, male_groups, ann_p, rec, male_rec):
    if pres == "male":
        return {"isBaseline": True}
    out = {"isBaseline": False, "measured": {}, "groupChanges": {}, "anatomical": [], "existingClothing": []}
    for k in ("shoulderWidthPx", "shoulderLineY", "waistLineY", "torsoLengthPx", "hipWidthPx", "legLengthPx", "hangingArmLengthPx"):
        a, b = m.get(k), male_m.get(k)
        if a is not None and b is not None:
            out["measured"][k] = {"value": a, "male": b, "delta": round(a - b, 1)}
        else:
            out["measured"][k] = {"value": a, "male": b, "delta": None,
                                  "note": "not comparable: landmark hidden or not applicable in one of the images"}
    for k, v in groups.items():
        if male_groups.get(k) != v:
            out["groupChanges"][k] = {"male": male_groups.get(k), "this": v}
    out["anatomical"] = list(ann_p.get("anatomy", []))
    out["existingClothing"] = list(ann_p.get("clothing", []))
    hidden_now = [k for k in ("hip", "kn") if rec["fields"][k]["imageLeft"]["status"] == "occluded"]
    hidden_male = [k for k in ("hip", "kn") if male_rec["fields"][k]["imageLeft"]["status"] == "occluded"]
    if hidden_now and not hidden_male and not any("hide" in c for c in out["existingClothing"]):
        out["existingClothing"].append("Existing clothing hides " + " and ".join({"hip": "hips", "kn": "knees"}[k] for k in hidden_now) + ".")
    sw = out["measured"]["shoulderWidthPx"]["delta"]
    if sw is not None and abs(sw) >= 60:
        out["anatomical"].append(f"Shoulder width differs from male by {sw:+.0f} px; male torso/sleeve art needs rescaling or a separate fit.")
    return out


# ---------------------------------------------------------------- build
def build(make_sheets=True):
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    recs = {(r["groupId"], r["presentation"]): r for r in notes_parser.load(HERE / "inspection-notes.txt")}
    observations, landmarks = [], []
    roster_ids = [g["id"] for g in roster["groups"]]
    HUMAN_MALE.update(metrics(recs[("human", "male")]))

    for g in roster["groups"]:
        gid = g["id"]
        ann = SPECIES.get(gid)
        per_pres = {}
        for pres in PRES:
            src = FRONTEND / g["imageVariants"][pres].lstrip("./")
            exists = src.exists()
            w, h = dimensions(src) if exists else (None, None)
            per_pres[pres] = dict(src=src, exists=exists, w=w, h=h, sha=sha256(src) if exists else None)

        if gid == "custom-lineage":
            for pres in PRES:
                p = per_pres[pres]
                observations.append({
                    "groupId": gid, "name": g["name"], "presentation": pres, "speciesIds": g["speciesIds"],
                    "priority": False,
                    "source": {"path": rel(p["src"]), "widthPx": p["w"], "heightPx": p["h"], "sha256": p["sha"],
                               "sharedAcrossPresentations": True},
                    "inspection": {"inspected": True, "method": "Rendered the SVG in headless Chromium and read its source.",
                                   "confidence": "high"},
                    "anatomy": {"bodyPlan": "none", "limbTopology": "No figure. A golden question-mark symbol (aria-label 'Custom lineage unknown ancestry symbol').",
                                "note": "There is no body to fit. A custom lineage would need a chosen base body plan from another species."},
                    "fitGroups": None, "differencesFromMale": {"isBaseline": pres == "male", "note": "Identical file for all presentations."},
                    "clearance": None,
                })
                landmarks.append({"groupId": gid, "presentation": pres, "source": {"path": rel(p["src"]), "sha256": p["sha"],
                                  "widthPx": p["w"], "heightPx": p["h"]}, "inspected": True,
                                  "noFigure": True, "landmarks": {}})
            continue

        male_rec = recs[(gid, "male")]
        male_m = metrics(male_rec)
        male_groups = None
        for pres in PRES:
            p = per_pres[pres]
            rec = recs.get((gid, pres))
            ann_p = ann["pres"].get(pres, {})
            m = metrics(rec)
            groups = {
                "torso": torso_group(ann["back"], m),
                "lowerBody": ann_p.get("lower", ann["lower"]),
                "sleeve": ann_p.get("sleeve", ann["sleeve"]),
                "hand": ann_p.get("hand", ann["hand"]),
                "footwear": ann_p.get("foot", ann["foot"]),
            }
            if pres == "male":
                male_groups = dict(groups)
            clearance = {k: None for k in ("horns", "ears", "wings", "tail", "shell", "hair", "beard", "other")}
            clearance.update(ann.get("clearance", {}))
            clearance.update(ann_p.get("clearance", {}))
            lms = landmarks_for(rec)
            n_unc = sum(1 for v in lms.values() if v["status"] in ("uncertain", "uncertain-unlocated"))
            n_occ = sum(1 for v in lms.values() if v["status"] == "occluded")
            conf = ann_p.get("confidence") or ann.get("confidence") or ("medium" if n_unc >= 3 else "high")
            observations.append({
                "groupId": gid, "name": g["name"], "presentation": pres, "speciesIds": g["speciesIds"],
                "priority": gid in PRIORITY,
                "source": {"path": rel(p["src"]), "widthPx": p["w"], "heightPx": p["h"], "sha256": p["sha"]},
                "inspection": {
                    "inspected": True,
                    "method": INSPECTION_METHOD + (" (zoomed crop used for this species)" if gid in ZOOMED else ""),
                    "confidence": conf,
                    "confidenceNote": "Body plan / limb topology: high unless stated. Landmarks: hand-placed, about "
                                      f"+/-{PRECISION_PX} px; {n_unc} uncertain, {n_occ} occluded.",
                },
                "anatomy": {"family": ann["family"], "observed": rec["anatomyNote"],
                            "hands": rec["hands"], "clothingAsDrawn": rec.get("clothingNote")},
                "metricsPx": m,
                "fitGroups": groups,
                "torsoGroupDerivation": torso_derivation(m),
                "placementVsHumanMale": placement(m),
                "differencesFromMale": diff_from_male(gid, pres, m, male_m, groups, male_groups, ann_p, rec, male_rec),
                "clearance": clearance,
            })
            landmarks.append({
                "groupId": gid, "presentation": pres,
                "source": {"path": rel(p["src"]), "sha256": p["sha"], "widthPx": p["w"], "heightPx": p["h"]},
                "inspected": True, "precisionPx": PRECISION_PX,
                "sideConvention": "imageLeft = viewer's left (the character's right side); imageRight = viewer's right.",
                "landmarks": lms,
            })

    unavailable = [{"groupId": k, "status": "unavailable-in-checkout", "inspected": False, "note": v}
                   for k, v in EXPECTED_UNAVAILABLE.items() if k not in roster_ids]
    meta = {
        "generatedBy": "tools/visual-catalog/fit-observations/build.py",
        "roster": rel(ROSTER), "rosterGroupCount": len(roster_ids), "presentations": PRES,
        "coordinateSpace": "original image pixels, origin top-left",
        "scope": "Analysis only. Fit groups are suggestions for which artwork could be shared; nothing here proves a layer fits.",
        "unreferencedImagesIgnored": sorted(
            str(Path("frontend/assets/species") / f.name) for f in (FRONTEND / "assets/species").iterdir()
            if f.name not in {Path(v).name for g in roster["groups"] for v in g["imageVariants"].values()}),
    }
    (HERE / "observations.json").write_text(json.dumps(
        {"meta": meta, "unavailable": unavailable, "observations": observations}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "landmarks.json").write_text(json.dumps(
        {"meta": dict(meta, statusValues=["visible", "uncertain", "occluded", "not-applicable", "uncertain-unlocated"]),
         "unavailable": unavailable, "images": landmarks}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"observations: {len(observations)}  landmark sets: {len(landmarks)}  unavailable: {[u['groupId'] for u in unavailable]}")
    if make_sheets:
        import contact_sheets
        n = contact_sheets.render(roster, observations, landmarks, HERE / "contact-sheets")
        print(f"contact sheets: {n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sheets", action="store_true")
    build(make_sheets=not ap.parse_args().no_sheets)
