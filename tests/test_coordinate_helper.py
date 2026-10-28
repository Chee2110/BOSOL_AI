import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import unittest
from app.pipeline.coordinate_helper import CoordinateHelper

class TestCoordinateHelper(unittest.TestCase):
    def test_rotation_0_roundtrip(self):
        cropbox = (0.0, 0.0, 595.0, 842.0)
        original_bbox = [100.0, 200.0, 300.0, 450.0]
        viewport_w, viewport_h = 1190.0, 1684.0 # Scale 2.0

        vp_bbox = CoordinateHelper.pdf_to_viewport(original_bbox, cropbox, 0, viewport_w, viewport_h)
        reconstructed = CoordinateHelper.viewport_to_pdf(vp_bbox, cropbox, 0, viewport_w, viewport_h)

        for orig, recon in zip(original_bbox, reconstructed):
            self.assertAlmostEqual(orig, recon, places=4)

    def test_rotation_90_roundtrip(self):
        cropbox = (0.0, 0.0, 595.0, 842.0)
        original_bbox = [50.0, 120.0, 250.0, 300.0]
        viewport_w, viewport_h = 1684.0, 1190.0

        vp_bbox = CoordinateHelper.pdf_to_viewport(original_bbox, cropbox, 90, viewport_w, viewport_h)
        reconstructed = CoordinateHelper.viewport_to_pdf(vp_bbox, cropbox, 90, viewport_w, viewport_h)

        for orig, recon in zip(original_bbox, reconstructed):
            self.assertAlmostEqual(orig, recon, places=4)

    def test_rotation_180_roundtrip(self):
        cropbox = (0.0, 0.0, 595.0, 842.0)
        original_bbox = [80.0, 150.0, 400.0, 600.0]
        viewport_w, viewport_h = 1190.0, 1684.0

        vp_bbox = CoordinateHelper.pdf_to_viewport(original_bbox, cropbox, 180, viewport_w, viewport_h)
        reconstructed = CoordinateHelper.viewport_to_pdf(vp_bbox, cropbox, 180, viewport_w, viewport_h)

        for orig, recon in zip(original_bbox, reconstructed):
            self.assertAlmostEqual(orig, recon, places=4)

    def test_rotation_270_roundtrip(self):
        cropbox = (0.0, 0.0, 595.0, 842.0)
        original_bbox = [70.0, 90.0, 320.0, 480.0]
        viewport_w, viewport_h = 1684.0, 1190.0

        vp_bbox = CoordinateHelper.pdf_to_viewport(original_bbox, cropbox, 270, viewport_w, viewport_h)
        reconstructed = CoordinateHelper.viewport_to_pdf(vp_bbox, cropbox, 270, viewport_w, viewport_h)

        for orig, recon in zip(original_bbox, reconstructed):
            self.assertAlmostEqual(orig, recon, places=4)

    def test_cropbox_offset_roundtrip(self):
        # Lệch tọa độ MediaBox vs CropBox (x0=36, y0=36)
        cropbox = (36.0, 36.0, 631.0, 878.0)
        original_bbox = [100.0, 150.0, 250.0, 350.0]
        viewport_w, viewport_h = 1190.0, 1684.0

        vp_bbox = CoordinateHelper.pdf_to_viewport(original_bbox, cropbox, 0, viewport_w, viewport_h)
        reconstructed = CoordinateHelper.viewport_to_pdf(vp_bbox, cropbox, 0, viewport_w, viewport_h)

        for orig, recon in zip(original_bbox, reconstructed):
            self.assertAlmostEqual(orig, recon, places=4)

    def test_max_error_is_zero(self):
        cropbox = (0.0, 0.0, 842.0, 1190.0) # A3
        bbox = [123.456, 234.567, 345.678, 456.789]
        
        for rot in (0, 90, 180, 270):
            vw = 1684.0 if rot in (0, 180) else 2380.0
            vh = 2380.0 if rot in (0, 180) else 1684.0
            vp = CoordinateHelper.pdf_to_viewport(bbox, cropbox, rot, vw, vh)
            recon = CoordinateHelper.viewport_to_pdf(vp, cropbox, rot, vw, vh)
            
            errors = [abs(a - b) for a, b in zip(bbox, recon)]
            max_err = max(errors)
            self.assertLess(max_err, 1e-4, f"Max error {max_err} vượt ngưỡng tại góc {rot}°")

if __name__ == "__main__":
    unittest.main()
