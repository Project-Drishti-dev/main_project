"""Throwaway smoke check for task 4.7.  Deleted when it has said what it says."""

import statistics
import sys

import cv2
import numpy as np

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests/unit")

import test_td1
import test_td2
import test_td3
from app.pipeline.tier0 import document, mrz_region

import test_mrz_region as t


def chain(image):
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(image))
    glyphs = mrz_region.filter_glyphs(mrz_region.extract_components(binary))
    return mrz_region.filter_lines(mrz_region.group_lines(glyphs))


def zone_page(texts, width=600, height=300, scale=0.7, pitch=70, x=20):
    image = np.full((height, width, 3), 255, np.uint8)
    for row, text in enumerate(texts):
        cv2.putText(image, text, (x, pitch * (row + 1)),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2,
                    cv2.LINE_AA)
    return image


TD1_ZONE = [test_td1.SPECIMEN_LINE_1, test_td1.SPECIMEN_LINE_2]
TD1_ZONE.append(test_td1.SPECIMEN_LINE_3)
TD2_ZONE = [test_td2.SPECIMEN_LINE_1, test_td2.SPECIMEN_LINE_2]
TD3_ZONE = [test_td3.SPECIMEN_LINE_1, test_td3.SPECIMEN_LINE_2]

ZONES = (("TD1", 3, 30, TD1_ZONE), ("TD2", 2, 36, TD2_ZONE),
         ("TD3", 2, 44, TD3_ZONE))

for name, count, length, texts in ZONES:
    lines = chain(zone_page(texts))
    counts = [len(line) for line in lines]
    median = statistics.median(counts)
    print(name, "drawn", [len(x) for x in texts], "blobs", counts,
          "median", median, "->", mrz_region.infer_format(lines))

print()
for label, frame in (("flat", t.upright_mrz()), ("dim", t.dim_mrz()),
                     ("grainy", t.grainy_mrz())):
    lines = chain(frame)
    print("fixture", label, [len(l) for l in lines], "->",
          mrz_region.infer_format(lines))

specks = mrz_region.filter_glyphs(
    mrz_region.extract_components(mrz_region.to_gray(t.upright_mrz()))
)
speck_lines = mrz_region.group_lines(specks)
print("specks", [len(l) for l in speck_lines], "->",
      mrz_region.infer_format(speck_lines))

stray = chain(t.stray_line_page(baseline=40))
print("stray near the leading", [len(l) for l in stray], "->",
      mrz_region.infer_format(stray))
print("empty", mrz_region.infer_format(()),
      "empty lines", mrz_region.infer_format(((), ())))

band = mrz_region.LINE_LENGTH_TOLERANCE
lengths = sorted(length for _, length in document.MRZ_SHAPES)
ambiguous = [n for n in range(61)
             if sum(abs(n - each) <= band for each in lengths) > 1]
print("ambiguous medians 0..60", ambiguous)
print("tolerance", band, "lengths", lengths, "smallest gap",
      min(b - a for a, b in zip(lengths, lengths[1:])))
