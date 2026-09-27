import pytest

from tier0.mrz_parse import parse, parse_td3, parse_td1, MRZParseError

ICAO_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
ICAO_LINE2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_parse_td3_fields():
    fields = parse_td3([ICAO_LINE1, ICAO_LINE2])
    assert fields.format == "TD3"
    assert fields.surname == "ERIKSSON"
    assert fields.given_names == "ANNA MARIA"
    assert fields.issuing_country == "UTO"
    assert fields.document_number == "L898902C3"
    assert fields.birth_date == "740812"
    assert fields.sex == "F"
    assert fields.expiry_date == "120415"


def test_parse_td3_wrong_line_count_raises():
    with pytest.raises(MRZParseError):
        parse_td3([ICAO_LINE1])


def test_parse_td3_wrong_width_raises():
    with pytest.raises(MRZParseError):
        parse_td3([ICAO_LINE1[:40], ICAO_LINE2])


def test_auto_detect_td3_from_raw_ocr_text():
    # Simulate what pytesseract.image_to_string actually returns: possible
    # leading/trailing blank lines, trailing newline, lowercase noise.
    raw = f"\n  {ICAO_LINE1.lower()}  \n{ICAO_LINE2}\n\n"
    fields = parse(raw)
    assert fields.format == "TD3"
    assert fields.document_number == "L898902C3"


def test_auto_detect_handles_ragged_ocr_width():
    # OCR sometimes drops or duplicates a trailing filler character.
    ragged_line1 = ICAO_LINE1[:-1]  # one char short
    ragged_line2 = ICAO_LINE2 + "<"  # one char long
    raw = ragged_line1 + "\n" + ragged_line2
    fields = parse(raw)
    assert fields.format == "TD3"
    assert fields.document_number == "L898902C3"


def test_parse_td1():
    # Constructed TD1 (ID card) MRZ, 3x30.
    l1 = "I<UTOD231458907<<<<<<<<<<<<<<<"[:30]
    l2 = "7408122F1204159UTO<<<<<<<<<<<6"[:30]
    l3 = "ERIKSSON<<ANNA<MARIA<<<<<<<<<<"[:30]
    fields = parse_td1([l1, l2, l3])
    assert fields.format == "TD1"
    assert fields.surname == "ERIKSSON"
    assert fields.given_names == "ANNA MARIA"
    assert fields.birth_date == "740812"
    assert fields.expiry_date == "120415"


def test_parse_raises_on_unrecognizable_garbage():
    with pytest.raises(MRZParseError):
        parse("this is not an mrz at all, just some ocr noise")
