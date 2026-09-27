"""
Builds a synthetic "passport photo page" image for exercising the full
Stage A (image -> MRZ text) pipeline without needing a real scanned
document. Renders a plausible page layout (photo block, printed fields,
some noise) with a monospaced MRZ strip along the bottom, then hands back
its file path.
"""
import random

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

MONO_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def _render_mrz_page(
    tmp_path,
    mrz_lines,
    filename="synthetic_passport.png",
    rotation_deg=0.0,
    add_noise=False,
):
    width, height = 900, 600
    img = Image.new("RGB", (width, height), color=(235, 232, 225))
    draw = ImageDraw.Draw(img)

    # Fake photo block, top-left.
    draw.rectangle([40, 40, 260, 300], fill=(180, 190, 200), outline=(0, 0, 0))

    # Fake printed personal-detail lines (visual zone), top-right area.
    text_font = ImageFont.truetype(MONO_FONT_PATH, 18)
    lines = [
        "Surname: ERIKSSON",
        "Given names: ANNA MARIA",
        "Date of birth: 12 AUG 1974",
        "Nationality: UTOPIA",
        "Date of expiry: 15 APR 2012",
    ]
    for i, line in enumerate(lines):
        draw.text((300, 60 + i * 30), line, fill=(20, 20, 20), font=text_font)

    # MRZ strip along the bottom.
    mrz_font = ImageFont.truetype(MONO_FONT_PATH, 26)
    mrz_top = height - 40 - (len(mrz_lines) * 34)
    for i, line in enumerate(mrz_lines):
        draw.text((45, mrz_top + i * 34), line, fill=(0, 0, 0), font=mrz_font)

    if add_noise:
        arr = np.array(img).astype(np.int16)
        noise = np.random.default_rng(42).normal(0, 6, arr.shape).astype(np.int16)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    if rotation_deg:
        img = img.rotate(rotation_deg, expand=True, fillcolor=(235, 232, 225))

    path = tmp_path / filename
    img.save(path)
    return str(path)


@pytest.fixture
def icao_example_passport_image(tmp_path):
    """A clean synthetic image of the canonical ICAO 9303 worked example."""
    lines = [
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
    ]
    return _render_mrz_page(tmp_path, lines)


@pytest.fixture
def icao_example_passport_image_noisy_skewed(tmp_path):
    """Same content, but with sensor noise and a slight rotation — closer to a phone photo."""
    lines = [
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
    ]
    return _render_mrz_page(
        tmp_path,
        lines,
        filename="noisy_skewed.png",
        rotation_deg=2.5,
        add_noise=True,
    )


@pytest.fixture
def valid_unexpired_passport_image(tmp_path):
    """
    A synthetic passport whose MRZ has correct check digits (computed via
    tier0.checksum itself) and an expiry date far in the future, so the
    full run_tier0() pipeline can reach a genuine PASS in tests.
    """
    from tier0.checksum import compute_check_digit

    doc_number = "X12345678"
    doc_cd = compute_check_digit(doc_number)
    birth_date = "900101"
    birth_cd = compute_check_digit(birth_date)
    expiry_date = "351231"  # far future, won't expire during test runs
    expiry_cd = compute_check_digit(expiry_date)
    # A realistic personal-number value (rather than 14 filler chars) --
    # a long unbroken run of the repeated '<' filler glyph right next to
    # the check digits is a known confusion trigger for the OCR pass, so
    # this also doubles as a more representative test document.
    optional_data = "1234567890<<<<"[:14]
    optional_cd = compute_check_digit(optional_data)
    composite_input = (
        doc_number + doc_cd + birth_date + birth_cd + expiry_date + expiry_cd + optional_data + optional_cd
    )
    composite_cd = compute_check_digit(composite_input)

    line1 = "P<UTOSMITH<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    line2 = (
        f"{doc_number}{doc_cd}UTO{birth_date}{birth_cd}M{expiry_date}{expiry_cd}"
        f"{optional_data}{optional_cd}{composite_cd}"
    )
    assert len(line1) == 44
    assert len(line2) == 44
    return _render_mrz_page(tmp_path, [line1, line2], filename="valid_passport.png")
