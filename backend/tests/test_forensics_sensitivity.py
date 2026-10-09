"""The image-forensics checks measured on tampered, image-bearing pages
(scripts/forensics_sensitivity.py). Guards the measured behaviour: no
false alarm on untouched or merely re-saved scans, and copy-paste of writing
caught most of the time. ELA's blindness to a re-saved edit is recorded here
as a fact, not hidden: see AIML_Deep_Analysis.md."""
import pytest

from scripts.forensics_sensitivity import evaluate

PER_KIND = 12


@pytest.fixture(scope="module")
def rows():
    return evaluate(PER_KIND)


def test_untouched_and_resaved_scans_raise_no_copy_move_alarm(rows):
    assert rows["clean"]["copy_move"] == 0
    assert rows["resaved"]["copy_move"] == 0


def test_ela_rarely_cries_wolf_on_controls(rows):
    # Measured on 48 control scans: 1 false alarm. Allow that, not more.
    assert rows["clean"]["ela"] + rows["resaved"]["ela"] <= 2


def test_copy_paste_of_writing_is_usually_caught(rows):
    # Measured 19/24. Misses are copies of low-detail areas.
    assert rows["copy_move"]["copy_move"] >= int(0.6 * PER_KIND)


def test_ela_is_applied_to_every_image_page(rows):
    assert all(r["ela_applicable"] == r["n"] for r in rows.values())


def test_ela_does_not_see_an_edit_saved_over_the_whole_page(rows):
    """Known limit, measured 0/48: when an edited page is saved once more as a
    whole, ELA's recompression signal is gone and text edges dominate what is
    left. If this ever starts catching them, update the documentation."""
    assert rows["splice"]["ela"] + rows["retype"]["ela"] <= 4
