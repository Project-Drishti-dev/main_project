import argparse
import json
import sys

import cv2
import numpy as np

V_MIN = 240
S_MAX = 50
MAX_TOTAL = 0.02
MAX_LARGEST = 0.01


def _order(pts):
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def find_card(img, min_area_frac=0.03):
    h, w = img.shape[:2]
    scale = min(1.0, 800.0 / max(h, w))
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img.copy()
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    sh, sw = gray.shape

    masks = []
    e = cv2.Canny(gray, 40, 120)
    e = cv2.dilate(e, np.ones((3, 3), np.uint8), iterations=2)
    masks.append(cv2.morphologyEx(e, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)))
    _, t = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    masks += [t, cv2.bitwise_not(t)]

    best, best_area = None, 0
    for m in masks:
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            a = cv2.contourArea(c) / float(sh * sw)
            if min_area_frac <= a <= 0.98 and a > best_area:
                best, best_area = c, a
    if best is None:
        return None
    peri = cv2.arcLength(best, True)
    approx = cv2.approxPolyDP(best, 0.02 * peri, True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        pts, method = approx.reshape(4, 2), "quad"
    else:
        pts, method = cv2.boxPoints(cv2.minAreaRect(best)), "rect"
    pts_full = _order(pts / scale)
    mg = 0.005
    touches = bool(((pts_full[:, 0] < mg * w) | (pts_full[:, 0] > (1 - mg) * w) |
                    (pts_full[:, 1] < mg * h) | (pts_full[:, 1] > (1 - mg) * h)).any())
    return {"pts": pts_full, "area_frac": float(best_area), "method": method, "touches_border": touches}


def _glare_mask(img_bgr):
    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 2] >= V_MIN) & (hsv[:, :, 1] <= S_MAX)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    card = find_card(img_bgr)
    region, valid = "whole frame (card not found)", np.ones((h, w), bool)
    if card is not None:
        mask = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(mask, card["pts"].astype(np.int32), 255)
        k = max(3, int(min(h, w) * 0.01)) | 1
        inner = cv2.erode(mask, np.ones((k, k), np.uint8))
        if inner.sum() > 0:
            valid, region = inner > 0, "card region"
    m[~valid] = 0
    return m, valid, region


def assess(img_bgr, mode="photo"):
    if mode == "scan":
        return {"module": "glare", "score": None, "unit": "fraction of the card covered by glare", "passed": None,
                "rule": "not applicable to flat scans / digital documents (no camera reflections)",
                "reasons": [], "details": {"mode": "scan"}}
    m, valid, region = _glare_mask(img_bgr)
    area = float(valid.sum())
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    areas = stats[1:, cv2.CC_STAT_AREA] if n > 1 else np.array([0])
    total = float(areas.sum() / area)
    largest = float(areas.max() / area)
    big_blobs = int((areas / area > 0.001).sum())

    reasons = []
    if total > MAX_TOTAL:
        reasons.append("glare_total_high")
    if largest > MAX_LARGEST:
        reasons.append("glare_blob_large")

    return {
        "module": "glare",
        "score": round(total, 4),
        "unit": "fraction of the card covered by glare (lower = better)",
        "passed": not reasons,
        "rule": f"PASS if total glare <= {MAX_TOTAL:.0%} and largest blob <= {MAX_LARGEST:.0%}",
        "reasons": reasons,
        "details": {"measured_on": region, "largest_blob_fraction": round(largest, 4),
                    "blobs_over_0.1pct": big_blobs},
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
    ap = argparse.ArgumentParser(description="Glare check for one image")
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = camera photo of a card (default); scan = flat/digital document (check skipped)")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    ap.add_argument("--save", help="save an overlay with glare regions in red")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img, mode=args.mode)
    print(json.dumps(res, indent=2)) if args.json else show(res)
    if args.save:
        m, _, _ = _glare_mask(img)
        out = img.copy()
        out[m > 0] = (0, 0, 255)
        cv2.imwrite(args.save, out)
        print("saved:", args.save)


if __name__ == "__main__":
    main()
