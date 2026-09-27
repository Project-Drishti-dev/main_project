import argparse
import json
import sys

import cv2
import numpy as np

CARD_WIDTH_MM = 85.6
CARD_ASPECT = 85.6 / 54.0
ASPECT_TOL = 0.15
PPI_MIN = 150
MIN_GLYPH_PX = 8


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


def _glyph_heights(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bw)
    hs = [st[cv2.CC_STAT_HEIGHT] for st in stats[1:]
          if 4 <= st[cv2.CC_STAT_HEIGHT] <= 0.08 * H and st[cv2.CC_STAT_WIDTH] <= 0.08 * W and st[cv2.CC_STAT_AREA] >= 6]
    return np.array(hs)


def _assess_scan(img_bgr):
    hs = _glyph_heights(img_bgr)
    rule = f"scan mode: PASS if median character height >= {MIN_GLYPH_PX} px (physical size unknown, so PPI is not used)"
    if len(hs) < 30:
        return {"module": "ppi", "score": None, "unit": "median character height, px", "passed": False,
                "rule": rule, "reasons": ["too_little_text_found"], "details": {"characters_found": int(len(hs))}}
    med = float(np.median(hs))
    reasons = [] if med >= MIN_GLYPH_PX else ["text_too_small"]
    return {
        "module": "ppi", "score": round(med, 1), "unit": "median character height, px (higher = more detail per character)",
        "passed": not reasons, "rule": rule, "reasons": reasons,
        "details": {"mode": "scan", "characters_found": int(len(hs)),
                    "height_p25_px": round(float(np.percentile(hs, 25)), 1),
                    "height_p75_px": round(float(np.percentile(hs, 75)), 1),
                    "image_size": f"{img_bgr.shape[1]}x{img_bgr.shape[0]}"},
    }


def assess(img_bgr, card_width_mm=CARD_WIDTH_MM, mode="photo"):
    if mode == "scan":
        return _assess_scan(img_bgr)
    card = find_card(img_bgr)
    if card is None:
        return {"module": "ppi", "score": None, "unit": "effective PPI of the card", "passed": False,
                "rule": f"PASS if effective PPI >= {PPI_MIN}", "reasons": ["card_not_found"],
                "details": {"image_size": f"{img_bgr.shape[1]}x{img_bgr.shape[0]}"}}
    tl, tr, br, bl = card["pts"]
    horiz = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
    vert = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0
    long_px, short_px = max(horiz, vert), min(horiz, vert)
    aspect = long_px / max(short_px, 1e-6)
    ppi = long_px / (card_width_mm / 25.4)

    reasons = []
    if ppi < PPI_MIN:
        reasons.append("resolution_too_low")
    if abs(aspect - CARD_ASPECT) / CARD_ASPECT > ASPECT_TOL:
        reasons.append("card_outline_uncertain")
    if card["touches_border"]:
        reasons.append("card_cut_off_outline_unreliable")

    return {
        "module": "ppi",
        "score": round(float(ppi), 1),
        "unit": "effective PPI of the card (higher = more detail)",
        "passed": not reasons,
        "rule": f"PASS if effective PPI >= {PPI_MIN} and outline aspect ratio looks like a card",
        "reasons": reasons,
        "details": {
            "card_long_side_px": round(float(long_px), 1),
            "measured_aspect_ratio": round(float(aspect), 3),
            "expected_aspect_ratio": round(CARD_ASPECT, 3),
            "card_area_fraction": round(card["area_frac"], 3),
            "outline_method": card["method"],
            "image_size": f"{img_bgr.shape[1]}x{img_bgr.shape[0]}",
        },
        "_pts": card["pts"],
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
    ap = argparse.ArgumentParser(description="Effective PPI check for one image")
    ap.add_argument("image")
    ap.add_argument("--card-width-mm", type=float, default=CARD_WIDTH_MM, help="real length of the card's long side")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = camera photo of a card (default); scan = flat/digital document: measures text height instead of PPI")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    ap.add_argument("--save", help="save the image with the detected card outline")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img, args.card_width_mm, mode=args.mode)
    pts = res.pop("_pts", None)
    print(json.dumps(res, indent=2)) if args.json else show(res)
    if args.save and pts is not None:
        out = img.copy()
        cv2.polylines(out, [pts.astype(np.int32)], True, (0, 255, 0), max(2, img.shape[1] // 300))
        cv2.imwrite(args.save, out)
        print("saved:", args.save)


if __name__ == "__main__":
    main()
