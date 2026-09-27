import argparse
import json
import re
import sys

import cv2
import numpy as np

EDGE_FRAC_MAX = 0.02
SOLID_EDGE = 0.90
ASPECT_TOL = 0.10
MIN_ELEMENTS = 4


def _ink_mask(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 6
    return keep[lab]


def _edge_fractions(img_bgr):
    ink = _ink_mask(img_bgr)
    h, w = ink.shape
    t = max(2, int(0.004 * min(h, w)))
    return {
        "top": float(ink[:t, :].any(axis=0).mean()),
        "bottom": float(ink[-t:, :].any(axis=0).mean()),
        "left": float(ink[:, :t].any(axis=1).mean()),
        "right": float(ink[:, -t:].any(axis=1).mean()),
    }


def _aadhaar_checklist(img_bgr):
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:
        return None, "skipped: pytesseract / the Tesseract program is not installed"

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    big = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    text = ""
    for psm in (3, 6, 11):
        text += " " + " ".join(pytesseract.image_to_string(big, config=f"--psm {psm}").split())
    low = text.lower()

    found = {
        "12-digit number": bool(re.search(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)", text)),
        "Government / UIDAI text": any(k in low for k in ("government of india", "unique identification",
                                                          "authority of india", "uidai")),
        "'Aadhaar' word": ("aadhaar" in low) or ("aadhar" in low),
        "date of birth": bool(re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", text)) or "dob" in low,
    }
    face = False
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if not casc.empty():
        m = max(20, int(0.05 * min(gray.shape)))
        face = len(casc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(m, m))) > 0
    found["face photo"] = bool(face)

    qr = False
    try:
        det = cv2.QRCodeDetector()
        qr = bool(det.detect(img_bgr)[0]) or bool(det.detect(cv2.resize(img_bgr, None, fx=2, fy=2))[0])
    except Exception:
        pass
    return {"counted": found, "qr_code_info_only": qr}, None


def assess(img_bgr, mode="photo", doc="any", expected_aspect=None):
    rule = (f"PASS if no edge has content chopped by the frame (> {EDGE_FRAC_MAX:.0%} of the edge)"
            + (f", aspect within {ASPECT_TOL:.0%} of {expected_aspect}" if expected_aspect else "")
            + (f", and >= {MIN_ELEMENTS}/5 Aadhaar elements found" if doc == "aadhaar" else ""))
    if mode != "scan":
        return {"module": "completeness", "score": None, "unit": "edges with content cut off (0 = none)",
                "passed": None, "rule": "N/A in photo mode: module 8 checks whether the card runs out of the frame",
                "reasons": [], "details": {"mode": mode}}

    h, w = img_bgr.shape[:2]
    fr = _edge_fractions(img_bgr)
    reasons, cut_sides, border_sides = [], [], []
    for side, f in fr.items():
        if f > SOLID_EDGE:
            border_sides.append(side)
        elif f > EDGE_FRAC_MAX:
            cut_sides.append(side)
            reasons.append(f"content_cut_at_{side}_edge")

    details = {"mode": "scan"}
    for side in ("top", "bottom", "left", "right"):
        details[f"edge_{side}_content"] = f"{fr[side]:.1%}"
    if border_sides:
        details["ignored_solid_border_sides"] = border_sides

    if expected_aspect:
        measured = max(h, w) / float(min(h, w))
        dev = abs(measured - expected_aspect) / expected_aspect
        details["aspect_measured"] = round(measured, 3)
        details["aspect_expected"] = expected_aspect
        if dev > ASPECT_TOL:
            reasons.append("aspect_ratio_off")

    if doc == "aadhaar":
        res, note = _aadhaar_checklist(img_bgr)
        if res is None:
            details["aadhaar_checklist"] = note
        else:
            n_found = sum(res["counted"].values())
            missing = [k for k, v in res["counted"].items() if not v]
            details["aadhaar_elements_found"] = f"{n_found}/5"
            details["aadhaar_missing"] = missing or "none"
            details["qr_code_detected (info only)"] = res["qr_code_info_only"]
            if n_found < MIN_ELEMENTS:
                reasons.append("aadhaar_elements_missing")

    return {"module": "completeness", "score": len(cut_sides), "unit": "edges with content cut off (0 = none)",
            "passed": not reasons, "rule": rule, "reasons": reasons, "details": details,
            "_edges": fr}


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
    ap = argparse.ArgumentParser(description="Completeness (cut / cropped) check for one image")
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["photo", "scan"], default="photo",
                    help="photo = N/A (see module 8); scan = flat/digital document (runs the checks)")
    ap.add_argument("--doc", choices=["any", "aadhaar"], default="any", help="aadhaar adds the element checklist")
    ap.add_argument("--expected-aspect", type=float, default=None,
                    help="expected long/short side ratio of the WHOLE image (card 1.586, A4 1.414)")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    ap.add_argument("--save", help="save the image with cut edges marked in red")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Cannot read image: {args.image}")
    res = assess(img, mode=args.mode, doc=args.doc, expected_aspect=args.expected_aspect)
    edges = res.pop("_edges", None)
    print(json.dumps(res, indent=2, default=str)) if args.json else show(res)
    if args.save and edges:
        out = img.copy()
        h, w = out.shape[:2]
        th = max(4, int(0.01 * min(h, w)))
        for side, f in edges.items():
            if EDGE_FRAC_MAX < f <= SOLID_EDGE:
                if side == "top":
                    cv2.rectangle(out, (0, 0), (w, th), (0, 0, 255), -1)
                elif side == "bottom":
                    cv2.rectangle(out, (0, h - th), (w, h), (0, 0, 255), -1)
                elif side == "left":
                    cv2.rectangle(out, (0, 0), (th, h), (0, 0, 255), -1)
                else:
                    cv2.rectangle(out, (w - th, 0), (w, h), (0, 0, 255), -1)
        cv2.imwrite(args.save, out)
        print("saved:", args.save)


if __name__ == "__main__":
    main()
