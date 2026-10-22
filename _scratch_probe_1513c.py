import sys, uuid
import cv2
import numpy as np

sys.path.insert(0, r"D:\sih\main_project\backend")

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, copy_move, deepfake, ela, flags, morph, noise_residual, stamp
from app.risk.weightsets import loader

SCREENING_ID = uuid.UUID("2f8a6d51-9b3c-4e07-8a1d-5c6e7f80912a")
WIDTH, HEIGHT = 256, 192
EDITED_BOX = (96, 56, 48, 48)


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


def _head(side=180):
    image = np.full((side, side, 3), 205, np.uint8)
    image[:, :] = (205, 190, 165)
    cv2.ellipse(image, (side // 2, side // 2), (52, 66), 0, 0, 360, (150, 165, 175), -1)
    cv2.circle(image, (side // 2 - 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.circle(image, (side // 2 + 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.ellipse(image, (side // 2, side // 2 + 40), (26, 10), 0, 0, 180, (60, 65, 70), 2)
    return image


def _form(seed=0, size=(900, 700)):
    rng = np.random.default_rng(seed)
    width, height = size
    page = np.full((height, width, 3), 236, np.uint8)
    for row in range(40, int(height * 0.78), 18):
        for column in range(40, int(width * 0.62), 18):
            if rng.random() < 0.12:
                continue
            cv2.line(page, (column, row), (column + 12, row), (70, 70, 70), 2, cv2.LINE_AA)
    cv2.rectangle(page, (int(width * 0.68), 60), (int(width * 0.94), int(height * 0.45)), (60, 60, 60), 2)
    page[70:250, int(width * 0.70):int(width * 0.70) + 180] = _head()
    lit = rng.poisson(np.clip(page.astype(np.float64), 0, None))
    noisy = np.clip(lit + rng.normal(0, 1.4, page.shape), 0, 255).astype(np.uint8)
    return cv2.imdecode(cv2.imencode(".jpg", noisy, [int(cv2.IMWRITE_JPEG_QUALITY), 85])[1], cv2.IMREAD_COLOR)


def _context(image):
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID, document_type="passport", image=image,
        reference_date=None, depth_mode=orchestrator.STANDARD,
    )


def overlap(box, other):
    if box is None:
        return 0.0
    ox0, oy0, ow, oh = other
    ix = max(0, min(box[2][0], ox0 + ow) - max(box[0][0], ox0))
    iy = max(0, min(box[2][1], oy0 + oh) - max(box[0][1], oy0))
    return (ix * iy) / float(ow * oh)


def main():
    page = _capture()
    shape = page.shape[:2]
    modules = [
        ("ela", ela.ELAModule()),
        ("noise", noise_residual.NoiseResidualModule()),
        ("copy_move", copy_move.CopyMoveModule()),
        ("stamp", stamp.StampModule()),
    ]
    run = base.DeepRun(ran=tuple(m.name for _, m in modules), results=tuple(m.run(_context(page)) for _, m in modules))
    built = flags.flags_from_run(run, shape=shape)
    for flag in built:
        print(f"{flag.id:34s} tier={flag.tier} band={flag.weight_band} value={flag.value:.4f} "
              f"conf={flag.confidence:.4f} region={flag.region} src={flag.source_module} field={flag.field}")
    ela_flag = built[0]
    print()
    print("VERIFY edited overlap:", f"{overlap(ela_flag.region, EDITED_BOX):.0%}")
    print("reason is the module sentence:", built[0].reason == run.results[0].detail)
    print("ids in weightset:", all(flag.id in loader.load_default().as_dict() for flag in built) if hasattr(loader, "load_default") else "n/a")

    form = _form()
    form_shape = form.shape[:2]
    portrait = [("morph", morph.MorphModule()), ("deepfake", deepfake.DeepfakeModule())]
    run2 = base.DeepRun(ran=tuple(m.name for _, m in portrait), results=tuple(m.run(_context(form)) for _, m in portrait))
    for flag in flags.flags_from_run(run2, shape=form_shape):
        print(f"{flag.id:34s} value={flag.value:.4f} region={flag.region}")

    # A module that located nothing itself and drew no map.
    bare = base.DeepResult(module=morph.MODULE_NAME, score=0.5, is_stub=True,
                           model_version="heuristic-v0", detail="d")
    print("bare morph region:", flags.flag_from_result(bare, shape=form_shape).region)

    # A hand-built map with one hot cell in the middle of a frame that is not a
    # whole number of blocks.
    cells = [[0.0] * 5 for _ in range(3)]
    cells[1][2] = 1.0
    mapped = base.DeepResult(module=ela.MODULE_NAME, score=1.0, is_stub=True,
                             model_version="ela-v0", detail="d", heatmap=tuple(map(tuple, cells)))
    for frame in ((16, 16), (17, 19), (23, 41)):
        print("frame", frame, "->", flags.region_from_result(mapped, frame))

    # A map nothing in reaches its level on.
    cold = dataclasses_replace(mapped, heatmap=((0.0,) * 5,) * 3)
    print("cold map ->", flags.region_from_result(cold, (16, 16)))


def dataclasses_replace(record, **changes):
    import dataclasses
    return dataclasses.replace(record, **changes)


main()
