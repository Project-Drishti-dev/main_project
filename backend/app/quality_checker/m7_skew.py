import argparse
import json
import math
import sys

import cv2
import numpy as np

MAX_SKEW_DEG = 10.0
MAX_PERSPECTIVE = 1.15


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


def _norm90(angle):
    return ((angle + 45.0) % 90.0) - 45.0


def _text_skew(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thr = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    pts = cv2.findNonZero(thr)
    if pts is None:
        return None
    return _norm90(cv2.minAreaRect(pts)[2])


def _scan_skew(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    s = 800.0 / max(h, w)
    if s < 1:
        gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        h, w = gray.shape
    _, bw = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    def sharp(angle):
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        r = cv2.warpAffine(bw, M, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(r.sum(axis=1).astype(np.float64)))

    best = max(np.arange(-15.0, 15.01, 1.0), key=sharp)
    best = max(np.arange(best - 1.0, best + 1.01, 0.2), key=sharp)
    return float(best)


def text_skew(img_bgr, mode="scan"):
    """The **signed** angle in degrees the text of this image sits at.

    ``assess`` reports ``abs()`` of this number, and that is the whole of what
    a quality gate needs: "is this straight enough" has no direction in it.  A
    caller that has to *act* on the angle rather than judge it does --
    ``app.pipeline.tier0.mrz_region.deskew`` rotates the working image upright
    before looking for the MRZ, and rotating the wrong way doubles the skew
    instead of removing it.  So the signed reading is published here rather
    than re-derived at the call site, which is the only way there is one
    answer to "how far round is this image".

    ``mode`` picks the estimator, and both are the ones this module already
    used: ``"scan"`` is the row-projection search over +/-15 degrees, which is
    the right reading for a flat or digital capture, and ``"photo"`` is the
    text-block ``minAreaRect``, which is what a camera photo of a document has
    always fallen back to when no card outline could be found.

    Returns ``None`` when the text-block estimator finds no text at all.  The
    scan estimator always returns a number, and on an image with no text in it
    that number sits on the edge of its search -- which is why a caller that
    acts on this angle has to bound it before it acts.
    """
    if mode == "scan":
        return _scan_skew(img_bgr)
    return _text_skew(img_bgr)


def _assess_scan(img_bgr):
    skew = text_skew(img_bgr, mode="scan")
    reasons = [] if abs(skew) <= MAX_SKEW_DEG else ["rotated"]
    return {
        "module": "skew", "score": round(abs(skew), 2), "unit": "estimated text skew in degrees (lower = straighter)",
        "passed": not reasons,
        "rule": f"scan mode: PASS if text skew <= {MAX_SKEW_DEG} deg (perspective not measured on flat scans)",
        "reasons": reasons, "details": {"mode": "scan", "method": "text-row projection profile"},
    }


def assess(img_bgr, mode="photo"):
    if mode == "scan":
        return _assess_scan(img_bgr)
    card = find_card(img_bgr)
    if card is not None:
        tl, tr, br, bl = card["pts"]
        top = math.degrees(math.atan2(tr[1] - tl[1], tr[0] - tl[0]))
        bot = math.degrees(math.atan2(br[1] - bl[1], br[0] - bl[0]))
        left = math.degrees(math.atan2(bl[1] - tl[1], bl[0] - tl[0])) - 90.0
        right = math.degrees(math.atan2(br[1] - tr[1], br[0] - tr[0])) - 90.0
        skew = float(np.mean([_norm90(a) for a in (top, bot, left, right)]))

        def ratio(a, b):
            return max(a, b) / max(min(a, b), 1e-6)
        persp = max(ratio(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)),
                    ratio(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        method = f"card outline ({card['method']})"
    else:
        skew = text_skew(img_bgr, mode="photo")
        persp = None
        method = "text-block fallback (rough)"
        if skew is None:
            return {"module": "skew", "score": None, "unit": "skew angle, degrees", "passed": False,
                    "rule": f"PASS if |skew| <= {MAX_SKEW_DEG} deg and perspective ratio <= {MAX_PERSPECTIVE}",
                    "reasons": ["could_not_measure"], "details": {}}

    reasons = []
    if abs(skew) > MAX_SKEW_DEG:
        reasons.append("rotated")
    if persp is not None and persp > MAX_PERSPECTIVE:
        reasons.append("photographed_at_angle")
    if card is not None and card["touches_border"]:
        reasons.append("card_cut_off_skew_unreliable")

    res = {
        "module": "skew",
        "score": round(abs(skew), 2),
        "unit": "absolute skew angle in degrees (lower = straighter)",
        "passed": not reasons,
        "rule": f"PASS if |skew| <= {MAX_SKEW_DEG} deg and perspective ratio <= {MAX_PERSPECTIVE}",
        "reasons": reasons,
        "details": {
            "signed_skew_deg": round(skew, 2),
            "perspective_ratio": None if persp is None else round(float(persp), 3),
            "method": method,
        },
    }
    if card is not None:
        res["_pts"] = card["pts"]
    return res


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
    ap = argparse.ArgumentParser(description="Skew/perspective check for one image")
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = camera photo of a card (default); scan = flat/digital document: skew from text rows")
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
