import argparse
import json
import sys

import cv2
import numpy as np

WORK_WIDTH = 800
MIN_RATIO = 0.60


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


def _illumination(img_bgr):
    card = find_card(img_bgr)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = WORK_WIDTH / float(w)
    gray = cv2.resize(gray, (WORK_WIDTH, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    k = int(max(gray.shape) * 0.06) | 1

    region, valid, work = "whole frame (card not found)", np.ones(gray.shape, bool), gray
    if card is not None:
        poly = (card["pts"] * scale).astype(np.int32)
        mask = np.zeros(gray.shape, np.uint8)
        cv2.fillConvexPoly(mask, poly, 255)
        inner = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k // 2 * 2 + 1, k // 2 * 2 + 1)))
        if inner.sum() > 0:
            work = gray.copy()
            work[mask == 0] = int(np.median(gray[inner > 0]))
            valid, region = inner > 0, "card region"

    bg = cv2.morphologyEx(work, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 2.0)
    return bg, valid, region


def assess(img_bgr, mode="photo"):
    bg, valid, region = _illumination(img_bgr)
    vals = bg[valid]
    p5, p95 = np.percentile(vals, [5, 95])
    ratio = float(p5 / max(p95, 1.0))
    cv = float(vals.std() / max(vals.mean(), 1.0))

    reasons = [] if ratio >= MIN_RATIO else ["uneven_lighting"]
    return {
        "module": "uniformity",
        "score": round(ratio, 3),
        "unit": "darkest/brightest illumination ratio (1.0 = perfectly even)",
        "passed": not reasons,
        "rule": f"PASS if p5/p95 illumination ratio >= {MIN_RATIO}",
        "reasons": reasons,
        "details": {
            "measured_on": region,
            "illumination_p5": round(float(p5), 1),
            "illumination_p95": round(float(p95), 1),
            "coefficient_of_variation": round(cv, 3),
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
    ap = argparse.ArgumentParser(description="Lighting uniformity check for one image")
    ap.add_argument("image")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    ap.add_argument("--save", help="save a color map of the illumination estimate to this path")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img)
    print(json.dumps(res, indent=2)) if args.json else show(res)
    if args.save:
        bg, valid, _ = _illumination(img)
        norm = cv2.normalize(bg, None, 0, 255, cv2.NORM_MINMAX)
        heat = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        heat[~valid] = (heat[~valid] * 0.25).astype(np.uint8)
        cv2.imwrite(args.save, heat)
        print("saved:", args.save)


if __name__ == "__main__":
    main()
