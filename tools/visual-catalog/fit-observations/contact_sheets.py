"""Annotated contact sheets for visual review of the hand-placed landmarks.

These are analysis artifacts (downscaled JPEGs with overlays), not app artwork.
Marker legend (also printed on each sheet):
  circle = visible   hollow circle = uncertain   (occluded points are listed, not drawn)
  wrist square = hand holding something non-cylindrical; wrist dot = empty hand
  dashed cyan line = waistline height
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 1 / 3
PW, PH = int(1024 * S), int(1536 * S)
GAP, HEAD, FOOT = 8, 22, 190
COLORS = {"shoulder": (255, 60, 60), "elbow": (255, 150, 0), "wrist": (255, 230, 0), "hip": (40, 220, 80),
          "knee": (60, 140, 255), "foot": (230, 60, 230), "hock": (255, 255, 255), "intertarsal": (255, 255, 255),
          "hoof": (230, 60, 230)}
BONES = [("shoulder", "elbow"), ("elbow", "wrist"), ("hip", "knee"), ("knee", "foot"), ("knee", "hock"), ("hock", "foot")]


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def render(roster, observations, landmarks, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.jpg"):
        old.unlink()
    f_small, f_head = _font(11), _font(13)
    obs = {(o["groupId"], o["presentation"]): o for o in observations}
    lms = {(l["groupId"], l["presentation"]): l for l in landmarks}
    root = Path(__file__).resolve().parents[3]
    n = 0
    for g in roster["groups"]:
        gid = g["id"]
        if gid == "custom-lineage":
            continue
        sheet = Image.new("RGB", (3 * PW + 4 * GAP, HEAD + PH + FOOT), (24, 24, 28))
        d = ImageDraw.Draw(sheet)
        for i, pres in enumerate(["male", "female", "androgynous"]):
            L = lms[(gid, pres)]
            o = obs[(gid, pres)]
            ox = GAP + i * (PW + GAP)
            im = Image.open(root / L["source"]["path"]).convert("RGB").resize((PW, PH))
            sheet.paste(im, (ox, HEAD))
            d.text((ox + 2, 4), f"{g['name']} - {pres}", fill=(240, 240, 240), font=f_head)
            pts = L["landmarks"]

            def xy(key):
                v = pts.get(key)
                if not v or v.get("x") is None:
                    return None
                return (ox + v["x"] * S, HEAD + v["y"] * S)

            for side in ("imageLeft", "imageRight"):
                for a, b in BONES:
                    pa, pb = xy(f"{a}.{side}"), xy(f"{b}.{side}")
                    if pa and pb:
                        d.line([pa, pb], fill=(200, 200, 200), width=1)
            pa, pb = xy("shoulder.imageLeft"), xy("shoulder.imageRight")
            if pa and pb:
                d.line([pa, pb], fill=COLORS["shoulder"], width=1)
            pa, pb = xy("hip.imageLeft"), xy("hip.imageRight")
            if pa and pb:
                d.line([pa, pb], fill=COLORS["hip"], width=1)
            w = pts.get("waist")
            if w and w.get("y"):
                y = HEAD + w["y"] * S
                for x in range(0, PW, 8):
                    d.line([(ox + x, y), (ox + x + 4, y)], fill=(0, 230, 230), width=1)
            occluded = []
            for key, v in pts.items():
                kind = key.split(".")[0]
                col = COLORS.get(kind, (255, 255, 255))
                p = xy(key)
                if p is None:
                    if v["status"] in ("occluded", "uncertain-unlocated"):
                        occluded.append(key.replace("imageLeft", "L").replace("imageRight", "R"))
                    continue
                r = 4
                box = [p[0] - r, p[1] - r, p[0] + r, p[1] + r]
                if kind == "wrist" and v.get("gripCategory", "").startswith("holding"):
                    d.rectangle(box, outline=col, width=2)
                elif v["status"] == "uncertain":
                    d.ellipse(box, outline=col, width=2)
                else:
                    d.ellipse(box, fill=col, outline=(0, 0, 0))
            fg = o["fitGroups"]
            lines = [f"torso  {fg['torso']}", f"lower  {fg['lowerBody']}", f"sleeve {fg['sleeve']}",
                     f"hand   {fg['hand']}", f"foot   {fg['footwear']}"]
            hands = o["anatomy"]["hands"]
            lines.append(f"hands L:{hands['imageLeft'][:26]}")
            lines.append(f"      R:{hands['imageRight'][:26]}")
            if occluded:
                lines += _wrap("not visible: " + ", ".join(occluded), 52)[:3]
            lines.append(f"confidence {o['inspection']['confidence']}")
            y = HEAD + PH + 4
            for ln in lines[:12]:
                d.text((ox + 2, y), ln[:58], fill=(220, 220, 220), font=f_small)
                y += 14
        d.text((GAP, sheet.height - 14),
               "ANALYSIS ONLY - not app art. dot=visible  ring=uncertain  square=non-cylindrical hold  "
               "cyan dashes=waist  coords: original px",
               fill=(150, 150, 150), font=f_small)
        sheet.save(outdir / f"{gid}.jpg", quality=80, optimize=True)
        n += 1
    return n
