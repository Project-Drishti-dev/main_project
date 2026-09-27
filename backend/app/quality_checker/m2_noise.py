import argparse
import json
import sys

import cv2
import numpy as np

SIGMA_MAX = 6.0

_K = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)


def _sigma(g):
    h, w = g.shape
    if h < 5 or w < 5:
        return 0.0
    c = cv2.filter2D(g, cv2.CV_64F, _K)
    return float(np.sqrt(np.pi / 2.0) * np.sum(np.abs(c[1:-1, 1:-1])) / (6.0 * (w - 2) * (h - 2)))


def _response(gray):
    return cv2.filter2D(gray, cv2.CV_64F, _K)[1:-1, 1:-1]


def assess(img_bgr, mode="photo"):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
    h, w = gray.shape
    r = np.abs(_response(gray))
    robust = float(1.4826 * np.median(r) / 6.0)
    whole = _sigma(gray)
    flat_fraction = float((r == 0).mean())

    reasons = [] if robust <= SIGMA_MAX else ["noisy"]
    return {
        "module": "noise",
        "score": round(robust, 2),
        "unit": "estimated noise std-dev, gray levels (lower = cleaner)",
        "passed": not reasons,
        "rule": f"PASS if robust noise sigma <= {SIGMA_MAX}",
        "reasons": reasons,
        "details": {
            "whole_image_sigma (inflated by text edges)": round(whole, 2),
            "perfectly_flat_pixel_fraction": round(flat_fraction, 3),
            "measured_at": f"native resolution {w}x{h}",
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
    ap = argparse.ArgumentParser(description="Noise check for one image")
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
