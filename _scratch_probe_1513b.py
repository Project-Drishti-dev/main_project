import sys, uuid
import cv2
import numpy as np

sys.path.insert(0, r"D:\sih\main_project\backend")

from app.pipeline import orchestrator
from app.pipeline.tier2 import copy_move, ela, noise_residual

SCREENING_ID = uuid.UUID("2f8a6d51-9b3c-4e07-8a1d-5c6e7f80912a")
WIDTH, HEIGHT = 256, 192
EDITED_BOX = (96, 56, 48, 48)
CONTROL_BOX = (16, 16, 48, 48)


def _jpeg(frame, quality):
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _smooth_page():
    across = np.linspace(30, 200, WIDTH, dtype=np.float64)
    down = np.linspace(30, 200, HEIGHT, dtype=np.float64)
    blue, green = np.meshgrid(across, down)
    ripple = np.cos(np.linspace(0, 3, HEIGHT)).reshape(-1, 1)
    red = 120.0 + 60.0 * np.sin(np.linspace(0, 3, WIDTH)) * ripple
    return np.clip(np.dstack([red, green, blue]), 0, 255).astype(np.uint8)


def _printed_patch(height, width):
    rng = np.random.default_rng(20261002)
    patch = np.full((height, width, 3), 235, np.uint8)
    for row in range(height // 6 + 1):
        cv2.putText(patch, "MRZ", (2, 6 + row * 6), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (15, 15, 15), 1, cv2.LINE_AA)
    grain = rng.integers(-30, 31, size=(height, width, 1)).astype(np.int16)
    return np.clip(patch.astype(np.int16) + grain, 0, 255).astype(np.uint8)


def _capture(patch_quality=30):
    page = _smooth_page()
    page[56:104, 96:144] = _jpeg(_printed_patch(48, 48), patch_quality)
    return _jpeg(page, 95)


def _context(image):
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID, document_type="passport", image=image,
        reference_date=None, depth_mode=orchestrator.STANDARD,
    )


def _peak_box(heatmap, shape, level):
    rows, cols = len(heatmap), len(heatmap[0])
    peak, r0, c0 = max((cell, r, c) for r, row in enumerate(heatmap) for c, cell in enumerate(row))
    if peak < level:
        return None, peak, 0
    seen, stack = {(r0, c0)}, [(r0, c0)]
    lo_r, hi_r, lo_c, hi_c = r0, r0, c0, c0
    while stack:
        r, c = stack.pop()
        lo_r, hi_r = min(lo_r, r), max(hi_r, r)
        lo_c, hi_c = min(lo_c, c), max(hi_c, c)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in seen and heatmap[nr][nc] >= level:
                seen.add((nr, nc)); stack.append((nr, nc))
    height, width = shape
    box = ((lo_c * width // cols, lo_r * height // rows), ((hi_c + 1) * width // cols, lo_r * height // rows),
           ((hi_c + 1) * width // cols, (hi_r + 1) * height // rows), (lo_c * width // cols, (hi_r + 1) * height // rows))
    return box, peak, len(seen)


def overlap(box, other):
    if box is None:
        return 0.0
    xs = [box[0][0], box[2][0]]; ys = [box[0][1], box[2][1]]
    ox0, oy0, ow, oh = other
    ix = max(0, min(xs[1], ox0 + ow) - max(xs[0], ox0)); iy = max(0, min(ys[1], oy0 + oh) - max(ys[0], oy0))
    return (ix * iy) / float(ow * oh)


def main():
    shape = (HEIGHT, WIDTH)
    for tag, page in (("clean-smooth", _capture(95)), ("tampered", _capture(30))):
        for name, module, level in (("ela", ela.ELAModule(), ela.HOT_LEVEL),
                                    ("noise", noise_residual.NoiseResidualModule(), noise_residual.HOT_LEVEL)):
            result = module.run(_context(page))
            box, peak, cells = _peak_box(result.heatmap, shape, level)
            hot = sum(1 for row in result.heatmap for c in row if c >= level)
            print(f"{name:6s} {tag:12s} score={result.score:.4f} hot={hot}/{len(result.heatmap)*len(result.heatmap[0])} "
                  f"peakbox={box} cells={cells} hit_edited={overlap(box, EDITED_BOX):.0%} hit_control={overlap(box, CONTROL_BOX):.0%}")

    page = _capture(30)
    grid = ela.ela_heatmap(page)
    print("grid", len(grid), "x", len(grid[0]), "frame", page.shape[:2])

    # A frame whose size is not a whole number of 8px blocks.
    odd = _jpeg(np.pad(page, ((0, 3), (0, 5), (0, 0)), mode="edge"), 95)
    odd_grid = ela.ela_heatmap(odd)
    box, peak, cells = _peak_box(odd_grid, odd.shape[:2], ela.HOT_LEVEL)
    h, w = odd.shape[:2]
    inside = box is not None and all(0 <= x <= w for x, _ in box) and all(0 <= y <= h for _, y in box)
    print("odd frame", odd.shape[:2], "grid", len(odd_grid), "x", len(odd_grid[0]), "box", box, "inside", inside)

    # Copy-move: a patch pasted twice inside one page.
    duplicate = page.copy()
    duplicate[120:168, 150:198] = page[56:104, 96:144]
    cm = copy_move.CopyMoveModule().run(_context(duplicate))
    print("copy_move score", round(cm.score, 4), "regions", len(cm.regions), "first", cm.regions[0] if cm.regions else None)


main()
