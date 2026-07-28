#!/usr/bin/env python3
"""
Rebuild gallery/photos.json from whatever is sitting in gallery/photos/.

Run by .github/workflows/gallery.yml whenever photos are pushed, so a photo
dragged onto github.com publishes itself — no access key, no manifest editing.

What it does:
  * shrinks anything bigger than MAX_EDGE px and re-encodes heavy JPEGs
  * adds an entry for each new photo, guessing caption and service from the
    filename
  * drops entries whose file has been deleted
  * leaves captions and services on existing entries alone, so anything typed
    in the Gallery Manager (or edited by hand) survives a rebuild
"""

import json
import os
import re
import sys
from datetime import date

from PIL import Image, ImageOps

PHOTO_DIR = "gallery/photos"
MANIFEST = "gallery/photos.json"
MAX_EDGE = 1600
QUALITY = 82
EXTS = (".jpg", ".jpeg", ".png", ".webp")

SERVICES = [
    "Lawns & Edging", "Gutter Cleaning", "Window Washing", "Pressure Washing",
    "Fencing", "Retaining Walls", "Walkways", "Seasonal Care",
]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


SERVICE_BY_SLUG = {slugify(s): s for s in SERVICES}
# The service-page filenames, since those are what you would naturally copy.
SERVICE_BY_SLUG.update({
    "lawns-and-edging": "Lawns & Edging", "gutter-cleaning": "Gutter Cleaning",
    "window-washing": "Window Washing", "pressure-washing": "Pressure Washing",
    "retaining-walls": "Retaining Walls", "seasonal-care": "Seasonal Care",
})
# A couple of shorthands people are likely to actually type.
SERVICE_BY_SLUG.update({
    "lawns": "Lawns & Edging", "lawn": "Lawns & Edging", "gutters": "Gutter Cleaning",
    "gutter": "Gutter Cleaning", "windows": "Window Washing", "window": "Window Washing",
    "pressure": "Pressure Washing", "washing": "Pressure Washing",
    "fence": "Fencing", "walls": "Retaining Walls", "wall": "Retaining Walls",
    "walkway": "Walkways", "seasonal": "Seasonal Care",
})


# Matches a camera-filename fragment: a known prefix (optionally run straight
# into digits, as in DSC00012) or a bare number.
CAMERA_WORD = re.compile(r"(?:img|dsc|dscn|pxl|photo|image|screenshot|jpe?g|png)\d*|\d+", re.I)


def parse_name(filename):
    """Guess a service and caption from a filename.

    'fencing__cedar-fence-rebuild-paisley.jpg' -> ('Fencing', 'Cedar fence rebuild paisley')
    'gutter-cleaning-hanover.jpg'              -> ('Gutter Cleaning', 'Hanover')
    'IMG_4821.jpg'                             -> ('Other', '')
    """
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)          # strip a date prefix

    rest = stem
    service = "Other"

    if "__" in stem:                                          # explicit separator wins
        head, rest = stem.split("__", 1)
        service = SERVICE_BY_SLUG.get(slugify(head), "Other")
    else:
        slug = slugify(stem)
        # Longest matching service prefix, so 'gutter-cleaning' beats 'gutter'.
        for cand in sorted(SERVICE_BY_SLUG, key=len, reverse=True):
            if slug == cand or slug.startswith(cand + "-"):
                service = SERVICE_BY_SLUG[cand]
                rest = slug[len(cand):]
                break

    words = [w for w in re.split(r"[-_\s]+", rest) if w]
    # A bare camera filename (IMG_4821, PXL_20240612_093301) is a poor caption,
    # so drop it and let the service name stand in.
    if words and all(CAMERA_WORD.fullmatch(w) or w.isdigit() for w in words):
        words = []
    caption = " ".join(words)
    caption = caption[:1].upper() + caption[1:] if caption else ""
    return service, caption


def process(path):
    """Shrink and re-encode in place when it helps.

    Returns (final_filename, width, height) — the name can change, since a png
    or webp is converted to jpg.
    """
    name = os.path.basename(path)
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)                       # honour phone rotation
        w, h = im.size
        before = os.path.getsize(path)
        scale = min(1.0, MAX_EDGE / max(w, h))
        needs_resize = scale < 1.0
        heavy = before > 600_000

        if not needs_resize and not heavy:
            return name, w, h

        if needs_resize:
            w, h = round(w * scale), round(h * scale)
            im = im.resize((w, h), Image.LANCZOS)

        out = os.path.splitext(path)[0] + ".jpg"
        im.convert("RGB").save(out, "JPEG", quality=QUALITY, optimize=True)

    if out != path:                                            # png/webp became jpg
        os.remove(path)
        print(f"  {name} -> {os.path.basename(out)} ({before // 1024}KB -> "
              f"{os.path.getsize(out) // 1024}KB, {w}x{h})")
        return os.path.basename(out), w, h

    after = os.path.getsize(path)
    if after >= before and not needs_resize:
        print(f"  {name} left alone (re-encoding gained nothing)")
    else:
        print(f"  {name} {before // 1024}KB -> {after // 1024}KB ({w}x{h})")
    return name, w, h


def main():
    if not os.path.isdir(PHOTO_DIR):
        print(f"No {PHOTO_DIR}/ directory; nothing to do.")
        return 0

    try:
        with open(MANIFEST) as f:
            listed = json.load(f).get("photos", [])
        existing = {p["file"]: p for p in listed}
        order = [p["file"] for p in listed]
    except (OSError, ValueError):
        existing, order = {}, []

    print("Processing photos…")
    dims = {}
    for f in sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(EXTS)):
        try:
            final, w, h = process(os.path.join(PHOTO_DIR, f))
            dims[final] = (w, h)
        except Exception as e:                                  # a dud file must not fail the run
            print(f"  !! skipping {f}: {e}", file=sys.stderr)

    # Re-list after processing, since png/webp will have become .jpg.
    files = sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(EXTS))

    known = [f for f in order if f in files]                    # keep curated order
    new = sorted(f for f in files if f not in known)            # newcomers on top

    photos = []
    for f in new + known:
        entry = dict(existing.get(f, {}))
        entry["file"] = f
        service, caption = parse_name(f)
        entry.setdefault("service", service)
        # Fall back to the service name, then to something neutral, so a photo
        # named IMG_4821.jpg never shows "Img 4821" to a customer.
        entry.setdefault("caption", caption or (service if service != "Other" else "Recent work"))
        if f in dims:
            entry["w"], entry["h"] = dims[f]
        entry.setdefault("added", date.today().isoformat())
        photos.append(entry)

    payload = {"photos": photos}
    new_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    old_text = open(MANIFEST).read() if os.path.exists(MANIFEST) else ""

    if new_text == old_text:
        print("Gallery listing already up to date.")
    else:
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w") as f:
            f.write(new_text)
        print(f"Gallery listing rebuilt: {len(photos)} photo(s).")
        for f in new:
            print(f"  + {f}")
        for f in order:
            if f not in files:
                print(f"  - {f} (file gone)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
