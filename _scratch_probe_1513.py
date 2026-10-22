import sys, uuid
import cv2
import numpy as np

sys.path.insert(0, r"D:\sih\main_project\backend")

from app.pipeline import orchestrator
from app.pipeline.tier2 import copy_move, deepfake, ela, morph, noise_residual, stamp

SCREENING_ID = uuid.UUID("2f8a6d51-9b3c-4e07-8a1d-5c6e7f80912a")


def _head(side=180, dx=0):
    image = np.full((side, side, 3), 205, np.uint8)
    image[:, :] = (205, 190, 165)
    cv2.ellipse(image, (side // 2 + dx, side // 2), (52, 66), 0, 0, 360, (150, 165, 175), -1)
    cv2.circle(image, (side // 2 + dx - 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.circle(image, (side // 2 + dx + 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.ellipse(image, (side // 2 + dx, side // 2 + 40), (26, 10), 0, 0, 180, (60, 65, 70), 2)
    return image


def _clean_page(seed=0, size=(900, 700)):
    rng = np.random.default_rng(seed)
    width, height = size
    page = np.full((height, width, 3), 236, np.uint8)
    for row in range(40, int(height * 0.78), 18):
        for column in range(40, int(width * 0.62), 18):
            if rng.random() < 0.12:
                continue
            cv2.line(page, (column, row), (column + 12, row), (70, 70, 70), 2, cv2.LINE_AA)
    for row in range(int(height * 0.82), int(height * 0.88), 24):
        cv2.line(page, (50, row), (int(width * 0.6), row), (90, 90, 90), 1, cv2.LINE_AA)
    cv2.rectangle(page, (int(width * 0.68), 60), (int(width * 0.94), int(height * 0.45)), (60, 60, 60), 2)
    photo_image = _head(180, int(rng.integers(-8, 9)))
    x, y = int(width * 0.70), 70
    page[y:y + 180, x:x + 180] = photo_image
    lit = rng.poisson(np.clip(page.astype(np.float64), 0, None))
    noisy = np.clip(lit + rng.normal(0, 1.4, page.shape), 0, 255).astype(np.uint8)
    encoded = cv2.imencode(".jpg", noisy, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return cv2.imdecode(encoded[1], cv2.IMREAD_COLOR)


def _jpeg(frame, quality):
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


EDITED = (300, 200, 120, 100)


def _tampered(page):
    """A page whose one rectangle was smoothed and re-encoded at a lower quality."""
    out = page.copy()
    x, y, w, h = EDITED
    patch = out[y:y + h, x:x + w]
    blurred = cv2.GaussianBlur(patch, (0, 0), 3.0)
    out[y:y + h, x:x + w] = _jpeg(blurred, 30)
    return _jpeg(out, 85)


def _context(image):
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _peak_box(heatmap, shape, level):
    """The candidate rule: the 4-connected group of hot cells holding the peak."""
    rows, cols = len(heatmap), len(heatmap[0])
    best = max(((cell, r, c) for r, row in enumerate(heatmap) for c, cell in enumerate(row)))
    peak, r0, c0 = best
    if peak < level:
        return None, peak
    seen = {(r0, c0)}
    stack = [(r0, c0)]
    lo_r, hi_r, lo_c, hi_c = r0, r0, c0, c0
    while stack:
        r, c = stack.pop()
        lo_r, hi_r = min(lo_r, r), max(hi_r, r)
        lo_c, hi_c = min(lo_c, c), max(hi_c, c)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in seen and heatmap[nr][nc] >= level:
                seen.add((nr, nc))
                stack.append((nr, nc))
    height, width = shape
    left, right = lo_c * width // cols, (hi_c + 1) * width // cols
    top, bottom = lo_r * height // rows, (hi_r + 1) * height // rows
    return ((int(left), int(top)), (int(right), int(top)), (int(right), int(bottom)), (int(left), int(bottom))), peak


def report(name, module, level, clean, dirty, shape):
    for tag, page in (("clean", clean), ("edited", dirty)):
        try:
            result = module.run(_context(page))
        except Exception as exc:
            print(f"{name:22s} {tag:6s} REFUSED {type(exc).__name__}: {exc}")
            continue
        gate = "FIRE" if result.score >= level else "    "
        hot = sum(1 for row in result.heatmap for cell in row if cell >= level)
        cells = len(result.heatmap) * len(result.heatmap[0]) if result.heatmap else 0
        extra = ""
        if result.regions:
            extra = f" regions={len(result.regions)} first={result.regions[0]}"
        if result.heatmap:
            box, peak = _peak_box(result.heatmap, shape, level)
            extra += f" hot={hot}/{cells} peakbox={box}"
        print(f"{name:22s} {tag:6s} {gate} score={result.score:.4f} level={level}{extra}")


def main():
    clean = _clean_page(seed=0)
    dirty = _tampered(_clean_page(seed=0))
    shape = clean.shape[:2]
    print("shape", shape, "edited", EDITED)
    print()
    report("tamper_ela", ela.ELAModule(), ela.HOT_LEVEL, clean, dirty, shape)
    report("tamper_noise_residual", noise_residual.NoiseResidualModule(), noise_residual.HOT_LEVEL, clean, dirty, shape)
    report("tamper_copy_move", copy_move.CopyMoveModule(), copy_move.HOT_LEVEL, clean, dirty, shape)
    report("tamper_stamp", stamp.StampModule(), stamp.MATCH_LEVEL, clean, dirty, shape)
    report("tamper_morph", morph.MorphModule(), morph.SUSPECT_LEVEL, clean, dirty, shape)
    report("tamper_deepfake", deepfake.DeepfakeModule(), deepfake.SUSPECT_LEVEL, clean, dirty, shape)


main()
