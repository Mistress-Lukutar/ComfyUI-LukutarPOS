'''
File:   test_rotate.py
Brief:  Rotation-mode resolution and auto quarter-turn geometry tests.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0
'''

from __future__ import annotations

import pytest
from comfyui_lukutar_pos.core import rotate


def test_auto_turns_portrait_image_for_landscape_target():
    """Portrait 2:3 on a landscape 3:2 label rotates 90 degrees."""
    assert rotate.auto_quarter_turns(200, 300, 300, 200) == 1
    assert rotate.auto_quarter_turns(300, 200, 200, 300) == 1


def test_auto_keeps_matching_orientations():
    """Landscape on landscape and portrait on portrait stay upright."""
    assert rotate.auto_quarter_turns(300, 200, 448, 320) == 0
    assert rotate.auto_quarter_turns(200, 300, 240, 832) == 0


def test_auto_keeps_squares():
    """A square on either side is a tie — turning gains nothing."""
    assert rotate.auto_quarter_turns(256, 256, 448, 320) == 0
    assert rotate.auto_quarter_turns(300, 200, 200, 200) == 0
    assert rotate.auto_quarter_turns(256, 256, 256, 256) == 0


def test_auto_compares_ratios_not_absolute_sizes():
    """Orientation disagreement always rotates, agreement never does.

    Turning swaps the ratio r for 1/r: when one side is portrait and
    the other landscape, |log r + log R| < |log r - log R| always
    holds, so the rule reduces to "rotate iff the orientations
    disagree" — even a very elongated mismatch keeps its orientation.
    """
    # A 1:4 image on a 1:2 target: both portrait, keep despite the
    # ratio gap.
    assert rotate.auto_quarter_turns(100, 400, 200, 400) == 0
    # A 1:2 image on a 2:1 target: turning matches exactly.
    assert rotate.auto_quarter_turns(100, 200, 200, 100) == 1


def test_resolve_fixed_modes():
    """Fixed modes map to counter-clockwise quarter turns."""
    assert rotate.resolve_rotation(rotate.ROTATE_NONE, 1, 2, 2, 1) == 0
    assert rotate.resolve_rotation(rotate.ROTATE_90_CCW, 1, 2, 2, 1) == 1
    assert rotate.resolve_rotation(rotate.ROTATE_180, 1, 2, 2, 1) == 2
    assert rotate.resolve_rotation(rotate.ROTATE_90_CW, 1, 2, 2, 1) == 3


def test_resolve_auto_turns_clockwise():
    """Auto reports the symmetric turn as 90 degrees clockwise (k=3)."""
    # Portrait 1:2 onto a landscape 2:1 target: a turn is needed.
    assert rotate.resolve_rotation(rotate.ROTATE_AUTO, 1, 2, 2, 1) == 3
    # Landscape onto landscape: no turn.
    assert rotate.resolve_rotation(rotate.ROTATE_AUTO, 2, 1, 2, 1) == 0


def test_bad_input_rejected():
    """Unknown modes and non-positive sizes raise."""
    with pytest.raises(ValueError, match="rotation mode"):
        rotate.resolve_rotation("spin", 100, 100, 100, 100)
    with pytest.raises(ValueError, match="positive"):
        rotate.auto_quarter_turns(0, 100, 100, 100)
