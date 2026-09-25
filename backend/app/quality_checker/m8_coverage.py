import argparse
import json
import sys

import cv2
import numpy as np

MARGIN_FRAC = 0.01
MIN_COVERAGE = 0.25
MAX_COVERAGE = 0.95


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


def assess(img_bgr, mode="photo"):
    if mode == "scan":
        return {"module": "coverage", "score": None, "unit": "card area / image area", "passed": None,
                "rule": "not applicable to flat scans / digital documents (the document fills the frame by design)",
                "reasons": [], "details": {"mode": "scan"}}
    h, w = img_bgr.shape[:2]
    rule = (f"PASS if all 4 corners are inside the frame (margin {MARGIN_FRAC:.0%}) "
            f"and card covers {MIN_COVERAGE:.0%}-{MAX_COVERAGE:.0%} of the image")
    card = find_card(img_bgr)
    if card is None:
        return {"module": "coverage", "score": None, "unit": "card area / image area", "passed": False,
                "rule": rule, "reasons": ["card_not_found"], "details": {}}

    pts = card["pts"]
    mx, my = MARGIN_FRAC * w, MARGIN_FRAC * h
    outside = [i for i, (x, y) in enumerate(pts) if x < mx or x > w - mx or y < my or y > h - my]
    names = ["top-left", "top-right", "bottom-right", "bottom-left"]
    quad_area = float(cv2.contourArea(pts.astype(np.float32))) / float(w * h)

    reasons = []
    if outside:
        reasons.append("card_cut_off_or_touching_edge")
    if quad_area < MIN_COVERAGE:
        reasons.append("card_too_small_in_frame")
    if quad_area > MAX_COVERAGE:
        reasons.append("card_fills_whole_frame")

    res = {
        "module": "coverage",
        "score": round(quad_area, 3),
        "unit": "card area / image area",
        "passed": not reasons,
        "rule": rule,
        "reasons": reasons,
        "details": {
            "corners_outside_or_at_edge": [names[i] for i in outside] or "none",
            "outline_method": card["method"],
        },
        "_pts": pts,
    }
    return res


def _verdict(res):
    return "N/A" if res["passed"] is None else ("PASS" if res["passed"] else "FAIL")


def show(res):
    s = res["score"]
    print(f"[{res['module']}]  score = {s}  ({res['unit']})  ->  {_verdict(res)}")
    print(f"  rule: {res['rule']}")
    for k, v in res["details"].items():
        print(f"  {k}: {v}")
    if res["reasons"]:
        print("  reasons:", ", ".join(res["reasons"]))


def main():
    ap = argparse.ArgumentParser(description="Card coverage/framing check for one image")
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = camera photo of a card (default); scan = flat/digital document (check skipped)")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    ap.add_argument("--save", help="save the image with the detected card outline")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img, mode=args.mode)
    pts = res.pop("_pts", None)
    print(json.dumps(res, indent=2)) if args.json else show(res)
    if args.save and pts is not None:
        out = img.copy()
        cv2.polylines(out, [pts.astype(np.int32)], True, (0, 255, 0), max(2, img.shape[1] // 300))
        cv2.imwrite(args.save, out)
        print("saved:", args.save)


if __name__ == "__main__":
    main()
