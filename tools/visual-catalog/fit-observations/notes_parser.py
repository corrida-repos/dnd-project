"""Parse inspection-notes.txt (hand-written while viewing the portraits).

Line format (one species/presentation per line, fields split on " | "):

    <groupId> <presentation> | <anatomy text> | sh .. | el .. | wr .. | hand L:<state> R:<state>
        | waist <y> | hip .. | kn .. | ft .. [extra text] [| clothing note]

Landmark field tokens:
    L<x>,<y>     visible point at image-left (viewer's left; the character's RIGHT side)
    R<x>,<y>     visible point at image-right (the character's LEFT side)
    <x>,<y>?     trailing "?" = uncertain estimate (shown, but low confidence)
    o / o(...)   occluded or not visible: no coordinate is recorded. A "~x,y"
                 inside the parentheses is only a note about where the hidden
                 part probably is and is never emitted as a coordinate.
    n/a          the landmark does not exist on this body plan
    (hock L.. R..) / (intertarsal ..)  extra digitigrade/avian joints
"""
import re

PT = r"(\d+),(\d+)(\?)?"
SIDE_RE = re.compile(r"\b([LR])\s?(o\b(?:\([^)]*\))?|n/a|\?|" + PT + r")")


def _point(tok, note=None):
    m = re.fullmatch(PT, tok)
    if m:
        x, y, q = int(m.group(1)), int(m.group(2)), m.group(3)
        d = {"status": "uncertain" if q else "visible", "x": x, "y": y}
    elif tok.startswith("o"):
        d = {"status": "occluded", "x": None, "y": None}
        inner = re.search(r"\(([^)]*)\)", tok)
        if inner:
            note = inner.group(1)
    elif tok == "n/a":
        d = {"status": "not-applicable", "x": None, "y": None}
    else:
        d = {"status": "uncertain-unlocated", "x": None, "y": None}
    if note:
        d["note"] = note
    return d


def parse_pair(body):
    """Return (left, right, rest_text)."""
    body = body.strip()
    trailing = None
    m = re.search(r"\(([^)]*)\)\s*$", body)
    # whole-field occlusion such as "o o (hands in pockets)" or "o(skirt) ~720"
    if re.match(r"^o(\b|\()", body):
        note = None
        mm = re.search(r"\(([^)]*)\)", body)
        if mm:
            note = mm.group(1)
        occ = {"status": "occluded", "x": None, "y": None}
        if note:
            occ = dict(occ, note=note)
        return dict(occ), dict(occ), body
    if body.startswith("n/a"):
        na = {"status": "not-applicable", "x": None, "y": None}
        mm = re.search(r"\(([^)]*)\)", body)
        if mm:
            na["note"] = mm.group(1)
        return dict(na), dict(na), body
    if body.startswith("?"):
        u = {"status": "uncertain-unlocated", "x": None, "y": None, "note": body}
        return dict(u), dict(u), body
    found = {}
    for mm in SIDE_RE.finditer(body):
        side, tok = mm.group(1), mm.group(2)
        if side in found:
            continue
        found[side] = _point(tok)
    left = found.get("L", {"status": "uncertain-unlocated", "x": None, "y": None})
    right = found.get("R", {"status": "uncertain-unlocated", "x": None, "y": None})
    return left, right, body


def parse_extra_joints(text):
    out = {}
    for name in ("hock", "intertarsal"):
        m = re.search(r"\(" + name + r"[^)]*\)", text)
        if m:
            l, r, _ = parse_pair(m.group(0)[len(name) + 1:-1])
            out[name] = {"imageLeft": l, "imageRight": r}
    return out


def parse_line(line):
    parts = [p.strip() for p in line.split(" | ")]
    gid, pres = parts[0].split()
    rec = {"groupId": gid, "presentation": pres, "anatomyNote": parts[1], "fields": {}, "extra": {}}
    clothing = []
    for p in parts[2:]:
        key, _, body = p.partition(" ")
        if key == "ft" and body.startswith("hooves"):
            na = {"status": "not-applicable", "x": None, "y": None,
                  "note": "quadruped: see extra.hooves"}
            rec["fields"][key] = {"imageLeft": dict(na), "imageRight": dict(na), "raw": body}
            hooves = []
            for i, m in enumerate(re.finditer(r"(fore|hind)\s?[LR]?(\d+),(\d+)", body)):
                hooves.append({"label": f"{m.group(1)}-{i + 1}", "status": "visible",
                               "x": int(m.group(2)), "y": int(m.group(3))})
            rec["extra"]["hooves"] = hooves
        elif key in ("sh", "el", "wr", "hip", "kn", "ft"):
            l, r, raw = parse_pair(body)
            rec["fields"][key] = {"imageLeft": l, "imageRight": r, "raw": raw}
            rec["extra"].update(parse_extra_joints(body))
        elif key == "hand":
            m = re.match(r"L:(\S+(?:\([^)]*\))?)\s+R:(.+)$", body)
            rec["hands"] = {"imageLeft": m.group(1), "imageRight": m.group(2).strip()}
        elif key == "waist":
            m = re.match(r"(\d+)", body)
            rec["waistY"] = int(m.group(1)) if m else None
        else:
            clothing.append(p)
    rec["clothingNote"] = "; ".join(clothing) or None
    return rec


def load(path):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            recs.append(parse_line(line))
    return recs


if __name__ == "__main__":
    import json, sys
    for r in load(sys.argv[1]):
        print(json.dumps(r)[:400])
