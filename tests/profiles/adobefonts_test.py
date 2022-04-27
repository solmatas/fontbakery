"""
Unit tests for Adobe Fonts profile.
"""
import os
from unittest.mock import patch

from fontTools.ttLib import TTFont

from fontbakery.checkrunner import WARN, FAIL, ERROR
from fontbakery.codetesting import (
    assert_PASS,
    assert_results_contain,
    CheckTester,
    portable_path,
    TEST_FILE,
)
from fontbakery.profiles import adobefonts as adobefonts_profile
from fontbakery.profiles.adobefonts import (
    ADOBEFONTS_PROFILE_CHECKS,
    OVERRIDDEN_CHECKS,
    profile,
    SET_EXPLICIT_CHECKS,
)

OVERRIDE_SUFFIX = ":adobefonts"


def test_get_family_checks():
    """Validate the set of family checks."""
    family_checks = profile.get_family_checks()
    family_check_ids = {check.id for check in family_checks}
    expected_family_check_ids = {
        "com.adobe.fonts/check/family/bold_italic_unique_for_nameid1",
        "com.adobe.fonts/check/family/consistent_upm",
        "com.adobe.fonts/check/family/max_4_fonts_per_family_name",
        "com.google.fonts/check/family/underline_thickness",
        "com.google.fonts/check/family/panose_proportion",
        "com.google.fonts/check/family/panose_familytype",
        "com.google.fonts/check/family/equal_unicode_encodings",
        "com.google.fonts/check/family/equal_font_versions",
        # "com.google.fonts/check/family/win_ascent_and_descent",
        "com.google.fonts/check/family/vertical_metrics",
        "com.google.fonts/check/family/single_directory",
        # should it be included here? or should we have
        # a get_superfamily_checks() method?
        # 'com.google.fonts/check/superfamily/vertical_metrics',
    }
    assert family_check_ids == expected_family_check_ids


def test_profile_check_set():
    """Confirm that the profile has the correct number of checks and the correct
    set of check IDs."""
    assert len(SET_EXPLICIT_CHECKS) == 76
    explicit_with_overrides = sorted(
        f"{check_id}{OVERRIDE_SUFFIX}" if check_id in OVERRIDDEN_CHECKS else check_id
        for check_id in SET_EXPLICIT_CHECKS
    )
    assert explicit_with_overrides == sorted(ADOBEFONTS_PROFILE_CHECKS)


def test_check_family_consistent_upm():
    """A group of fonts designed & produced as a family should have consistent
    units per em."""
    check = CheckTester(
        adobefonts_profile, "com.adobe.fonts/check/family/consistent_upm"
    )

    # these fonts have a consistent unitsPerEm of 1000:
    filenames = [
        "SourceSansPro-Regular.otf",
        "SourceSansPro-Bold.otf",
        "SourceSansPro-Italic.otf",
    ]
    fonts = [
        os.path.join(portable_path("data/test/source-sans-pro/OTF"), filename)
        for filename in filenames
    ]

    # try fonts with consistent UPM (i.e. 1000)
    assert_PASS(check(fonts))

    ttFonts = check["ttFonts"]
    # now try with one font with a different UPM (i.e. 2048)
    ttFonts[1]["head"].unitsPerEm = 2048
    assert_results_contain(check(ttFonts), FAIL, "inconsistent-upem")


def test_check_find_empty_letters():
    """Validate that empty glyphs are found."""
    check = CheckTester(adobefonts_profile, "com.adobe.fonts/check/find_empty_letters")

    PASS_MSG = "No empty glyphs for letters found."

    # this OT-CFF font has inked glyphs for all letters
    ttFont = TTFont(TEST_FILE("source-sans-pro/OTF/SourceSansPro-Regular.otf"))
    assert assert_PASS(check(ttFont)) == PASS_MSG

    # this OT-CFF2 font has inked glyphs for all letters
    ttFont = TTFont(TEST_FILE("source-sans-pro/VAR/SourceSansVariable-Italic.otf"))
    assert assert_PASS(check(ttFont)) == PASS_MSG

    # this TrueType font has inked glyphs for all letters
    ttFont = TTFont(TEST_FILE("source-sans-pro/TTF/SourceSansPro-Bold.ttf"))
    assert assert_PASS(check(ttFont)) == PASS_MSG

    # Add 2 Korean hangul syllable characters to cmap table mapped to the 'space' glyph.
    # These characters are part of the set whose glyphs are allowed to be blank.
    # The check should only yield a WARN.
    for cmap_table in ttFont["cmap"].tables:
        if cmap_table.format != 4:
            cmap_table.cmap[0xB646] = "space"
            cmap_table.cmap[0xD7A0] = "space"
    msg = assert_results_contain(check(ttFont), WARN, "empty-hangul-letter")
    assert msg == "Found 2 empty hangul glyph(s)."

    # this font has empty glyphs for several letters,
    # the first of which is 'B' (U+0042)
    ttFont = TTFont(TEST_FILE("familysans/FamilySans-Regular.ttf"))
    msg = assert_results_contain(check(ttFont), FAIL, "empty-letter")
    assert msg == "U+0042 should be visible, but its glyph ('B') is empty."


def _get_nameid_1_win_eng_record(name_table):
    """Helper method that returns the Windows nameID 1 US-English record"""
    for rec in name_table.names:
        if (rec.nameID, rec.platformID, rec.platEncID, rec.langID) == (1, 3, 1, 0x409):
            return rec
    return None


def test_check_nameid_1_win_english():
    """Validate that font has a good nameID 1, Windows/Unicode/US-English
    `name` table record."""
    check = CheckTester(
        adobefonts_profile, "com.adobe.fonts/check/nameid_1_win_english"
    )

    ttFont = TTFont(TEST_FILE("source-sans-pro/OTF/SourceSansPro-Regular.otf"))
    msg = assert_PASS(check(ttFont))
    assert msg == "Font contains a good Windows nameID 1 US-English record."

    name_table = ttFont["name"]
    nameid_1_win_eng_rec = _get_nameid_1_win_eng_record(name_table)

    # Replace the nameID 1 string with an empty string
    nameid_1_win_eng_rec.string = ""
    msg = assert_results_contain(check(ttFont), FAIL, "nameid-1-empty")
    assert msg == "Windows nameID 1 US-English record is empty."

    # Replace the nameID 1 string with data that can't be 'utf_16_be'-decoded
    nameid_1_win_eng_rec.string = "\xff".encode("utf_7")
    msg = assert_results_contain(check(ttFont), ERROR, "nameid-1-decoding-error")
    assert msg == "Windows nameID 1 US-English record could not be decoded."

    # Delete all 'name' table records
    name_table.names = []
    msg = assert_results_contain(check(ttFont), FAIL, "nameid-1-not-found")
    assert msg == "Windows nameID 1 US-English record not found."

    # Delete 'name' table
    del ttFont["name"]
    msg = assert_results_contain(check(ttFont), FAIL, "name-table-not-found")
    assert msg == "Font has no 'name' table."


def test_check_whitespace_glyphs_adobefonts_override():
    """Check that overridden test for nbsp yields WARN rather than FAIL."""
    check = CheckTester(
        adobefonts_profile, f"com.google.fonts/check/whitespace_glyphs{OVERRIDE_SUFFIX}"
    )

    ttFont = TTFont(TEST_FILE("source-sans-pro/OTF/SourceSansPro-Regular.otf"))
    assert_PASS(check(ttFont))

    # remove U+00A0, status should be WARN (standard check would be FAIL)
    for subtable in ttFont["cmap"].tables:
        subtable.cmap.pop(0x00A0, None)
    assert_results_contain(check(ttFont), WARN, "missing-whitespace-glyph-0x00A0")


def test_check_valid_glyphnames_adobefonts_override():
    """Check that overridden test yields WARN rather than FAIL."""
    check = CheckTester(
        adobefonts_profile, f"com.google.fonts/check/valid_glyphnames{OVERRIDE_SUFFIX}"
    )

    ttFont = TTFont(TEST_FILE("nunito/Nunito-Regular.ttf"))
    assert_PASS(check(ttFont))

    good_name = "b" * 63
    bad_name1 = "a" * 64
    bad_name2 = "3cents"
    bad_name3 = ".threecents"
    ttFont.glyphOrder[2] = bad_name1
    ttFont.glyphOrder[3] = bad_name2
    ttFont.glyphOrder[4] = bad_name3
    ttFont.glyphOrder[5] = good_name
    message = assert_results_contain(check(ttFont), WARN, "found-invalid-names")
    assert good_name not in message
    assert bad_name1 in message
    assert bad_name2 in message
    assert bad_name3 in message


@patch("freetype.Face", side_effect=ImportError)
def test_check_freetype_rasterizer_adobefonts_override(mock_import_error):
    """Check that overridden test yields ERROR rather than SKIP."""
    check = CheckTester(
        adobefonts_profile,
        f"com.adobe.fonts/check/freetype_rasterizer{OVERRIDE_SUFFIX}",
    )

    font = TEST_FILE("cabin/Cabin-Regular.ttf")
    msg = assert_results_contain(check(font), ERROR, "freetype-not-installed")
    assert "FreeType is not available" in msg
