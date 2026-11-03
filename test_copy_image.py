import os
import unittest
from core.clipboard import make_hdrop_bytes, _dropfiles_header, png_to_data_uri

class TestCopyImageHelpers(unittest.TestCase):
    def test_dropfiles_header(self):
        hdr = _dropfiles_header()
        self.assertEqual(len(hdr), 20)
        # fWide is at offset 16 (BOOL, 4 bytes), should be non-zero (True)
        # pFiles is at offset 0 (DWORD, 4 bytes), should be 20
        pFiles = int.from_bytes(hdr[0:4], "little")
        self.assertEqual(pFiles, 20)

    def test_make_hdrop_bytes(self):
        paths = ["C:\\test\\1.png", "C:\\test\\2.png"]
        b = make_hdrop_bytes(paths)
        self.assertTrue(b.startswith(_dropfiles_header()))
        # Check double null termination at the end
        self.assertTrue(b.endswith(b"\0\0"))
        # Verify decoding of paths portion
        paths_data = b[20:]
        decoded = paths_data.decode("utf-16-le")
        parts = decoded.split("\0")
        # parts should contain "C:\test\1.png", "C:\test\2.png", and empty strings due to trailing nulls
        self.assertIn("C:\\test\\1.png", parts)
        self.assertIn("C:\\test\\2.png", parts)

    def test_make_hdrop_empty_raises(self):
        with self.assertRaises(ValueError):
            make_hdrop_bytes([])

    def test_png_to_data_uri(self):
        # Create a tiny temporary dummy image or file
        temp_path = "temp_test_img.png"
        with open(temp_path, "wb") as f:
            # minimal valid PNG header/bytes or arbitrary bytes for test
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)
        try:
            uri = png_to_data_uri(temp_path)
            self.assertTrue(uri.startswith("data:image/png;base64,"))
            self.assertGreater(len(uri), 22)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
