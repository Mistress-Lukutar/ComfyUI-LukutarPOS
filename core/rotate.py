'''
File:   rotate.py
Brief:  Optimal quarter-turn selection for images going onto a label.
Author: Mistress-Lukutar
Date:   2026-09-03
Version: v0.1.0

A portrait photo placed on a landscape label wastes most of the box
(or gets cropped to a sliver) unless it is turned 90 degrees first.
This module picks the turn by comparing aspect ratios — it is pure
geometry, so it works on any width/height pair without touching the
pixels (torch-free, like the rest of ``core``).
'''

from __future__ import annotations

import math

#: Pick the turn automatically from the aspect ratios.
ROTATE_AUTO = "auto"
#: Never rotate.
ROTATE_NONE = "0"
#: Quarter turn clockwise.
ROTATE_90_CW = "90 cw"
#: Quarter turn counter-clockwise.
ROTATE_90_CCW = "90 ccw"
#: Half turn (upside down).
ROTATE_180 = "180"
#: Selectable rotation modes.
ROTATE_MODES: tuple[str, ...] = (
    ROTATE_AUTO,
    ROTATE_NONE,
    ROTATE_90_CW,
    ROTATE_90_CCW,
    ROTATE_180,
)

#: Mode -> quarter turns counter-clockwise (np.rot90 / torch.rot90 k).
_TURNS: dict[str, int] = {
    ROTATE_NONE: 0,
    ROTATE_90_CCW: 1,
    ROTATE_180: 2,
    ROTATE_90_CW: 3,
}


def auto_quarter_turns(
    image_w: int, image_h: int, target_w: int, target_h: int
) -> int:
    '''Pick 0 or 1 quarter turn to match the target's aspect ratio.

    A 90-degree turn swaps width and height, turning the image's aspect
    ratio r into 1/r. The turn is taken exactly when it brings the
    ratio closer to the target's, comparing in log space so that 2:1
    and 1:2 are equally "wide":

    - portrait image vs landscape target (and vice versa) -> turn;
    - matching orientations -> keep;
    - a square on either side is a tie -> keep (a turn would gain
      nothing geometrically).

    Args:
        image_w: Image width in pixels.
        image_h: Image height in pixels.
        target_w: Target box/label width in the same units.
        target_h: Target box/label height.

    Returns:
        0 to keep, 1 for a 90-degree turn. The direction is
        geometrically irrelevant — turning either way swaps the axes.

    Raises:
        ValueError: On a non-positive dimension.
    '''
    if min(image_w, image_h, target_w, target_h) <= 0:
        raise ValueError("image and target sizes must be positive")
    image_ratio = math.log(image_w / image_h)
    target_ratio = math.log(target_w / target_h)
    mismatch_keep = abs(image_ratio - target_ratio)
    mismatch_turn = abs(image_ratio + target_ratio)
    return 1 if mismatch_turn < mismatch_keep else 0


def resolve_rotation(
    mode: str, image_w: int, image_h: int, target_w: int, target_h: int
) -> int:
    '''Resolve a rotation mode into counter-clockwise quarter turns.

    ``auto`` turns 90 degrees clockwise (3 CCW quarter turns): the
    direction is geometrically symmetric, and reporting a 90-degree
    turn reads better than 270.

    Args:
        mode: One of :data:`ROTATE_MODES`.
        image_w: Image width in pixels (used by ``auto``).
        image_h: Image height in pixels.
        target_w: Target width (used by ``auto``).
        target_h: Target height.

    Returns:
        Quarter turns counter-clockwise, 0..3 (the ``k`` of
        ``np.rot90`` / ``torch.rot90``).

    Raises:
        ValueError: On an unknown mode or non-positive size.
    '''
    if mode == ROTATE_AUTO:
        return (-auto_quarter_turns(image_w, image_h, target_w, target_h)) % 4
    try:
        return _TURNS[mode]
    except KeyError:
        raise ValueError(f"unknown rotation mode: {mode!r}") from None
