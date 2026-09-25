import argparse
import json
import sys

import cv2
import numpy as np

MEAN_RANGE = (60, 225)
MAX_DARK_CLIP = 0.05
MAX_BRIGHT_CLIP = 0.10
MIN_CONTRAST = 50


def assess(img_bgr, mode="photo"):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mean = float(gray.mean())
    p5, p95 = np.percentile(gray, [5, 95])
    contrast = float(p95 - p5)
    dark_clip = float((gray <= 5).mean())
    bright_clip = float((gray >= 250).mean())

    reasons = []
    if mean < MEAN_RANGE[0]:
        reasons.append("too_dark")
    if mode == "photo" and mean > MEAN_RANGE[1]:
        reasons.append("too_bright")
    if dark_clip > MAX_DARK_CLIP:
        reasons.append("shadows_clipped")
    if mode == "photo" and bright_clip > MAX_BRIGHT_CLIP:
        reasons.append("highlights_clipped")
    if contrast < MIN_CONTRAST:
        reasons.append("low_contrast")

    return {
        "module": "exposure",
        "score": round(mean, 1),
        "unit": "mean brightness, 0-255 (ideal: mid-range)",
        "passed": not reasons,
        "rule": ((f"PASS if mean in {MEAN_RANGE}, dark-clip <= {MAX_DARK_CLIP:.0%}, "
                  f"bright-clip <= {MAX_BRIGHT_CLIP:.0%}, contrast >= {MIN_CONTRAST}") if mode == "photo" else
                 (f"scan mode: PASS if mean >= {MEAN_RANGE[0]}, dark-clip <= {MAX_DARK_CLIP:.0%}, "
                  f"contrast >= {MIN_CONTRAST} (white paper allowed)")),
        "reasons": reasons,
        "details": {
            "mode": mode,
            "contrast_p95_minus_p5": round(contrast, 1),
            "dark_clipped_fraction": round(dark_clip, 4),
            "bright_clipped_fraction": round(bright_clip, 4),
        },
    }


def _verdict(res):
    return "N/A" if res["passed"] is None else ("PASS" if res["passed"] else "FAIL")


def show(res):
    print(f"[{res['module']}]  score = {res['score']}  ({res['unit']})  ->  {_verdict(res)}")
    print(f"  rule: {res['rule']}")
    for k, v in res["details"].items():
        print(f"  {k}: {v}")
    if res["reasons"]:
        print("  reasons:", ", ".join(res["reasons"]))


def main():
    ap = argparse.ArgumentParser(description="Exposure check for one image")
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = camera photo of a card (default); scan = flat/digital document, white paper is normal")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img, mode=args.mode)
    print(json.dumps(res, indent=2)) if args.json else show(res)


if __name__ == "__main__":
    main()
