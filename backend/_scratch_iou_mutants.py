import io, re, shutil, subprocess, sys, os

target = os.path.join("tests", "fixtures", "evaluation.py")
backup = target + ".bak"
shutil.copyfile(target, backup)
original = open(backup, encoding="utf-8").read()

MUTANTS = {
    "iou over intersection only": (
        "    union = _area(one) + _area(other) - shared\n    return shared / union if union else 0.0",
        "    return shared",
    ),
    "iou ignoring the union it dilutes": (
        "    union = _area(one) + _area(other) - shared\n    return shared / union if union else 0.0",
        "    union = _area(one) + _area(other)\n    return shared / union if union else 0.0",
    ),
    "overlap measured over every injection": (
        "            if hit:\n                best = _best_overlap(reading.alerts, kind, injection[\"box\"])",
        "            if True:\n                best = _best_overlap(reading.alerts, kind, injection[\"box\"])",
    ),
    "worst alert scored rather than the best": (
        "    return max(\n        (iou(alert.box, box) for alert in alerts if alert.label == kind),\n        default=0.0,\n    )",
        "    return min(\n        (iou(alert.box, box) for alert in alerts if alert.label == kind),\n        default=0.0,\n    )",
    ),
    "a missing box measured as one": (
        "    if one is None or other is None:\n        return 0.0",
        "    if one is None:\n        one = other\n    if other is None:\n        return 0.0",
    ),
    "an empty mean reported as a zero": (
        "        if not self.count:\n            return None\n        return self.total / self.count",
        "        return self.total / self.count if self.count else 0.0",
    ),
    "localized counted over every injection": (
        "                localized += best >= OVERLAP_THRESHOLD",
        "                localized += injection is not None",
    ),
    "half-open boxes closed": (
        "        max(0, min(one[2], other[2]) - max(one[0], other[0]))\n        * max(0, min(one[3], other[3]) - max(one[1], other[1]))",
        "        max(0, min(one[2], other[2]) - max(one[0], other[0]) + 1)\n        * max(0, min(one[3], other[3]) - max(one[1], other[1]) + 1)",
    ),
}

print(f"{'mutant':<44} result")
for name, (before, after) in MUTANTS.items():
    if before not in original:
        print(f"{name:<44} ANCHOR MISSING")
        continue
    open(target, "w", encoding="utf-8").write(original.replace(before, after, 1))
    run = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/unit/test_evaluation_region.py", "-q", "-p", "no:faulthandler", "-x"],
        capture_output=True, text=True,
    )
    tail = [l for l in run.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l]
    print(f"{name:<44} RED ({tail[-1] if tail else 'no summary'})" if run.returncode else f"{name:<44} *** GREEN ***")

shutil.copyfile(backup, target)
os.remove(backup)
restored = open(target, encoding="utf-8").read()
print("restored byte for byte:", restored == original)