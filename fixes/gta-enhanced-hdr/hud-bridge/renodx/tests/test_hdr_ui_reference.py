"""Independent vectors/properties; these do not execute or validate a shader."""
import math
import random
import unittest
from unittest import mock

import hdr_ui_reference as ref


class ReferenceTests(unittest.TestCase):
    def assertRgbClose(self, actual, expected, tolerance=1e-6):
        for channel, wanted in zip(actual, expected):
            self.assertAlmostEqual(channel, wanted, delta=tolerance)

    def controls(self, gamma=1, white=203, peak=10000):
        return ref.RenoControls(gamma, white, peak)

    def test_controls_are_required_and_invalid_controls_are_rejected(self):
        with self.assertRaises(TypeError):
            ref.RenoControls()
        for values in ((3, 203, 1000), (1, 0, 1000), (1, math.nan, 1000), (1, 203, 10001)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ref.RenoControls(*values)

    def test_standard_pq_vectors_and_roundtrips(self):
        vectors = ((80, 0.4858567654), (100, 0.5080784215), (203, 0.5806888810),
                   (400, 0.6525785976), (1000, 0.7518270962), (10000, 1.0))
        for nits, expected in vectors:
            with self.subTest(nits=nits):
                self.assertAlmostEqual(ref.pq_encode_nits(nits), expected, delta=1e-10)
                self.assertAlmostEqual(ref.pq_decode_nits(expected), nits, delta=max(1e-6, nits * 2e-9))
        self.assertEqual(ref.pq_decode_nits(0), 0)

    def test_current_gamma_control_changes_midgray(self):
        srgb = ref.compose_staged((0, 0, 0), (0.5, 0.5, 0.5), 1,
                                  self.controls(0), alpha_mode="straight")
        gamma22 = ref.compose_staged((0, 0, 0), (0.5, 0.5, 0.5), 1,
                                     self.controls(1), alpha_mode="straight")
        self.assertRgbClose(srgb.nits, (43.4503515179,) * 3)
        self.assertRgbClose(gamma22.nits, (44.1804410873,) * 3)
        self.assertGreater(gamma22.nits[0], srgb.nits[0])

    def test_alpha_zero_calls_original_path_without_ui_math(self):
        controls = self.controls()
        scene = (2.0, 0.1, 1.0)
        sentinel = object()
        with mock.patch.object(ref, "original_reno_path", return_value=sentinel) as original:
            result = ref.compose_staged(scene, (math.nan,) * 3, 0, controls,
                                        alpha_mode="unknown")
        self.assertIs(result, sentinel)
        original.assert_called_once_with(scene, controls)

    def test_missing_ui_uses_original_path_without_reading_ui_metadata(self):
        controls = self.controls()
        sentinel = object()
        with mock.patch.object(ref, "original_reno_path", return_value=sentinel):
            result = ref.compose_staged((1, 2, 3), (), math.nan, controls,
                                        alpha_mode="unknown", ui_present=False)
        self.assertIs(result, sentinel)

    def test_alpha_zero_matches_original_float_output_exactly(self):
        controls = self.controls(1, 203, 1000)
        scene = (2.1, 0.74, 1.2)
        expected = ref.original_reno_path(scene, controls)
        actual = ref.compose_staged(scene, (100, -100, 20), 0, controls, alpha_mode="straight")
        self.assertEqual(actual, expected)

    def test_alpha_one_does_not_read_or_depend_on_scene(self):
        controls = self.controls()
        expected = ref.compose_staged((0, 0, 0), (1, 1, 1), 1, controls, alpha_mode="straight")
        other = ref.compose_staged((math.nan,) * 3, (1, 1, 1), 1, controls, alpha_mode="straight")
        self.assertEqual(other, expected)
        self.assertRgbClose(other.nits, (203,) * 3)

    def test_opaque_and_half_white_203_nit_vectors(self):
        controls = self.controls()
        opaque = ref.compose_staged((0, 0, 0), (1, 1, 1), 1, controls, alpha_mode="straight")
        half = ref.compose_staged((0, 0, 0), (0.5, 0.5, 0.5), 0.5, controls,
                                  alpha_mode="encoded_premultiplied")
        self.assertRgbClose(opaque.nits, (203,) * 3)
        self.assertRgbClose(opaque.pq, (0.5806888810,) * 3, 1e-9)
        self.assertRgbClose(half.nits, (101.5,) * 3)
        self.assertRgbClose(half.pq, (0.5095734437,) * 3, 1e-9)

    def test_half_white_over_1000_nits_keeps_above_one_scene(self):
        controls = self.controls()
        encoded_scene = ref.encode_rgb((1000 / 203,) * 3, controls)
        self.assertTrue(all(value > 1 for value in encoded_scene))
        result = ref.compose_staged(encoded_scene, (0.5, 0.5, 0.5), 0.5, controls,
                                    alpha_mode="encoded_premultiplied")
        self.assertRgbClose(result.nits, (601.5,) * 3)
        self.assertRgbClose(result.pq, (0.6965645113,) * 3, 1e-9)

    def test_runtime_white_is_applied_once_and_scene_remains_in_nits(self):
        for white in (48, 100, 203, 400, 500):
            controls = self.controls(1, white)
            scene = ref.encode_rgb((1000 / white,) * 3, controls)
            opaque = ref.compose_staged(scene, (1, 1, 1), 1, controls, alpha_mode="straight")
            half = ref.compose_staged(scene, (1, 1, 1), 0.5, controls, alpha_mode="straight")
            self.assertRgbClose(opaque.nits, (white,) * 3)
            self.assertRgbClose(half.nits, ((1000 + white) / 2,) * 3)

    def test_encoded_premultiplied_is_unpremultiplied_before_decode(self):
        controls = self.controls()
        correct = ref.compose_staged((0, 0, 0), (0.5,) * 3, 0.5, controls,
                                     alpha_mode="encoded_premultiplied")
        wrong_decode_first = ref.decode_component(0.5, controls) * 203
        self.assertRgbClose(correct.nits, (101.5,) * 3)
        self.assertGreater(correct.nits[0] - wrong_decode_first, 50)
        with self.assertRaises(ValueError):
            ref.compose_staged((0, 0, 0), (0.5,) * 3, 0.5, controls,
                                alpha_mode="unspecified_premultiplication_domain")

    def test_bt709_to_bt2020_uses_linear_color_and_preserves_white(self):
        red = ref.bt709_to_bt2020((1, 0, 0))
        self.assertRgbClose(red, (0.6274038959, 0.0690972894, 0.0163914389), 1e-12)
        self.assertRgbClose(ref.bt709_to_bt2020((1, 1, 1)), (1, 1, 1), 2e-10)
        result = ref.compose_staged((0, 0, 0), (1, 0, 0), 1, self.controls(), alpha_mode="straight")
        self.assertRgbClose(result.nits, (127.3629908677, 14.0267497482, 3.3274620967))
        encoded_first = ref.bt709_to_bt2020((0.5, 0, 0))
        wrong = ref.decode_rgb(encoded_first, self.controls())
        correct = ref.bt709_to_bt2020(ref.decode_rgb((0.5, 0, 0), self.controls()))
        self.assertGreater(max(abs(a - b) for a, b in zip(wrong, correct)), 0.02)

    def test_peak_limit_scales_channels_together(self):
        controls = self.controls(1, 203, 400)
        result = ref.finish_linear709((10, 2, 1), controls)
        unbounded = ref.bt709_to_bt2020((10, 2, 1))
        self.assertAlmostEqual(max(result.nits), 400)
        ratios = [a / b for a, b in zip(result.nits, unbounded)]
        self.assertRgbClose(ratios, (ratios[0],) * 3)

    def test_property_staged_matches_independent_absolute_nits_blend(self):
        rng = random.Random(0x20322)
        for index in range(600):
            controls = self.controls(index % 3, rng.choice((48, 80, 100, 203, 400, 500)))
            scene_linear = tuple(rng.uniform(0, 8) for _ in range(3))
            ui_encoded = tuple(rng.uniform(0, 1) for _ in range(3))
            alpha = rng.uniform(0.0001, 1)
            scene_encoded = ref.encode_rgb(scene_linear, controls)
            scene_nits = tuple(value * controls.graphics_white_nits
                               for value in ref.bt709_to_bt2020(scene_linear))
            expected = ref.compose_absolute_nits(scene_nits, ref.decode_rgb(ui_encoded, controls), alpha, controls)
            straight = ref.compose_staged(scene_encoded, ui_encoded, alpha, controls, alpha_mode="straight")
            premul = ref.compose_staged(scene_encoded, tuple(value * alpha for value in ui_encoded), alpha,
                                        controls, alpha_mode="encoded_premultiplied")
            with self.subTest(index=index):
                self.assertRgbClose(straight.nits, expected.nits, 1e-8)
                self.assertRgbClose(premul.nits, expected.nits, 1e-8)
                self.assertRgbClose(premul.pq, expected.pq, 1e-10)

    def test_property_no_roundtrip_needed_for_linear_staging(self):
        rng = random.Random(0xC010)
        for gamma in (0, 1, 2):
            controls = self.controls(gamma)
            for _ in range(100):
                linear = tuple(rng.uniform(0, 8) for _ in range(3))
                direct = ref.finish_linear709(linear, controls)
                roundtrip = ref.original_reno_path(ref.encode_rgb(linear, controls), controls)
                self.assertRgbClose(direct.nits, roundtrip.nits, 1e-8)
                self.assertRgbClose(direct.pq, roundtrip.pq, 1e-10)


if __name__ == "__main__":
    unittest.main()
