import argparse
import json
import sys

import cv2
import numpy as np

NORM_WIDTH = 1000
LAP_MIN = 100.0


def assess(img_bgr, mode="photo"):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    interp = cv2.INTER_AREA if w > NORM_WIDTH else cv2.INTER_CUBIC
    gray = cv2.resize(gray, (NORM_WIDTH, max(1, int(h * NORM_WIDTH / w))), interpolation=interp)

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(gx ** 2 + gy ** 2))

    reasons = [] if lap_var >= LAP_MIN else ["blurry"]
    return {
        "module": "sharpness",
        "score": round(lap_var, 1),
        "unit": "Laplacian variance (higher = sharper)",
        "passed": not reasons,
        "rule": f"PASS if Laplacian variance >= {LAP_MIN}",
        "reasons": reasons,
        "details": {"tenengrad": round(tenengrad, 1), "measured_at_width_px": NORM_WIDTH},
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
    ap = argparse.ArgumentParser(description="Sharpness check for one image")
    ap.add_argument("image")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img)
    print(json.dumps(res, indent=2)) if args.json else show(res)


if __name__ == "__main__":
    main()
