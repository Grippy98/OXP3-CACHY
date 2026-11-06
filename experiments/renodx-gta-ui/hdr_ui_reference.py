"""Independent CPU reference for the agreed GTA/RenoDX UI composition contract.

Math only: no texture reads, HLSL compilation, GPU calls or game configuration.
Inputs are BT.709 RGB in the CURRENT RenoDX intermediate transfer function.
UI alpha is linear coverage. Encoded-premultiplied UI was multiplied AFTER
encoding. An FP16 container alone does not establish this input contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

RGB = tuple[float, float, float]

# D65 BT.709 -> D65 BT.2020, computed from the published primary matrices.
BT709_TO_BT2020 = (
    (0.6274038959, 0.3292830384, 0.0433130657),
    (0.0690972894, 0.9195403951, 0.0113623156),
    (0.0163914389, 0.0880133079, 0.8955952532),
)


@dataclass(frozen=True)
class RenoControls:
    # The current GTA addon maps 0 -> sRGB, 1 -> gamma 2.2, 2 -> gamma 2.4.
    # All controls are required; 203 nits and gamma 2.2 are not defaults here.
    gamma_correction: int
    graphics_white_nits: float
    peak_white_nits: float

    def __post_init__(self):
        if self.gamma_correction not in (0, 1, 2):
            raise ValueError("Unsupported current RenoDX GammaCorrection value")
        for value in (self.graphics_white_nits, self.peak_white_nits):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("White/peak controls must be finite positive nits")
        if self.peak_white_nits > 10000:
            raise ValueError("Reference PQ domain is limited to 10000 nits")


@dataclass(frozen=True)
class Output:
    nits: RGB
    pq: RGB


def _rgb(values: Sequence[float]) -> RGB:
    result = tuple(float(value) for value in values)
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise ValueError("Expected three finite RGB values")
    return result


def _signed_power(value: float, power: float) -> float:
    return math.copysign(abs(value) ** power, value)


def decode_component(encoded: float, controls: RenoControls) -> float:
    if controls.gamma_correction == 0:
        magnitude = abs(encoded)
        linear = magnitude / 12.92 if magnitude <= 0.04045 else ((magnitude + 0.055) / 1.055) ** 2.4
        return math.copysign(linear, encoded)
    return _signed_power(encoded, 2.2 if controls.gamma_correction == 1 else 2.4)


def encode_component(linear: float, controls: RenoControls) -> float:
    if controls.gamma_correction == 0:
        magnitude = abs(linear)
        encoded = 12.92 * magnitude if magnitude <= 0.0031308 else 1.055 * magnitude ** (1 / 2.4) - 0.055
        return math.copysign(encoded, linear)
    return _signed_power(linear, 1 / (2.2 if controls.gamma_correction == 1 else 2.4))


def decode_rgb(encoded: Sequence[float], controls: RenoControls) -> RGB:
    return tuple(decode_component(value, controls) for value in _rgb(encoded))


def encode_rgb(linear: Sequence[float], controls: RenoControls) -> RGB:
    return tuple(encode_component(value, controls) for value in _rgb(linear))


def bt709_to_bt2020(linear: Sequence[float]) -> RGB:
    values = _rgb(linear)
    return tuple(sum(coefficient * value for coefficient, value in zip(row, values))
                 for row in BT709_TO_BT2020)


def pq_encode_nits(nits: float) -> float:
    if not math.isfinite(nits) or not 0 <= nits <= 10000:
        raise ValueError("PQ input must be finite and within 0..10000 nits")
    power = (nits / 10000) ** (2610 / 16384)
    return ((3424 / 4096 + (2413 / 128) * power) / (1 + (2392 / 128) * power)) ** (2523 / 32)


def pq_decode_nits(code: float) -> float:
    if not math.isfinite(code) or not 0 <= code <= 1:
        raise ValueError("PQ code must be finite and within 0..1")
    power = code ** (32 / 2523)
    return 10000 * (max(power - 3424 / 4096, 0) / (2413 / 128 - (2392 / 128) * power)) ** (16384 / 2610)


def _finish_nits(nits: Sequence[float], peak: float) -> Output:
    # Pinned GTA preset clamps negative BT.2020 components, then uniformly
    # scales channels if their maximum exceeds the configured peak.
    positive = tuple(max(0.0, value) for value in _rgb(nits))
    scale = min(1.0, peak / max(positive)) if max(positive) > 0 else 1.0
    bounded = tuple(value * scale for value in positive)
    return Output(bounded, tuple(pq_encode_nits(value) for value in bounded))


def finish_linear709(linear: Sequence[float], controls: RenoControls) -> Output:
    transformed = bt709_to_bt2020(linear)
    return _finish_nits(tuple(value * controls.graphics_white_nits for value in transformed),
                        controls.peak_white_nits)


def original_reno_path(scene_encoded709: Sequence[float], controls: RenoControls) -> Output:
    """Relevant pinned GTA SwapChainPass stages, before dithering/quantization."""
    return finish_linear709(decode_rgb(scene_encoded709, controls), controls)


def compose_staged(scene_encoded709: Sequence[float], ui_encoded709: Sequence[float],
                   alpha: float, controls: RenoControls, *,
                   alpha_mode: str, ui_present: bool = True) -> Output:
    """Decode/blend, then reuse the final pass with its decoding set to NONE.

    This models the agreed GTA preset (BT.709 intermediate, BT.2020 clamp,
    HDR10 output, no extra swap-chain gamma-correction step). It does not
    describe arbitrary RenoDX presets or assume the real UI resource is valid.
    """
    if not ui_present:
        return original_reno_path(scene_encoded709, controls)
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Alpha must be finite linear coverage within 0..1")
    if alpha == 0:
        return original_reno_path(scene_encoded709, controls)
    if alpha_mode not in ("straight", "encoded_premultiplied"):
        raise ValueError("Premultiplication domain must be explicitly known")
    encoded = _rgb(ui_encoded709)
    straight = tuple(value / alpha for value in encoded) if alpha_mode == "encoded_premultiplied" else encoded
    ui_linear = decode_rgb(straight, controls)
    if alpha == 1:
        return finish_linear709(ui_linear, controls)
    scene_linear = decode_rgb(scene_encoded709, controls)
    mixed = tuple((1 - alpha) * scene + alpha * ui for scene, ui in zip(scene_linear, ui_linear))
    return finish_linear709(mixed, controls)


def compose_absolute_nits(scene_bt2020_nits: Sequence[float], ui_straight_linear709: Sequence[float],
                          alpha: float, controls: RenoControls) -> Output:
    """Independent formulation: transform/scale the UI, blend in absolute nits."""
    scene = _rgb(scene_bt2020_nits)
    ui = bt709_to_bt2020(ui_straight_linear709)
    source_nits = tuple(value * controls.graphics_white_nits for value in ui)
    mixed_nits = tuple(scene_channel * (1 - alpha) + ui_channel * alpha
                       for scene_channel, ui_channel in zip(scene, source_nits))
    return _finish_nits(mixed_nits, controls.peak_white_nits)
