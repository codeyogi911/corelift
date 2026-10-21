import tempfile
import unittest
from pathlib import Path

from scripts.check_release import check_files


class ReleaseCheckTests(unittest.TestCase):
    def test_binary_file_is_scanned_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'shot.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00')
            check_files([image])

    def test_private_path_inside_binary_metadata_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'shot.png'
            # Split so this test file does not itself trip the release scan.
            image.write_bytes(b'\x89PNG\r\n\x1a\ntEXtSource/' + b'Users' + b'/someone/Desktop\x00')
            with self.assertRaisesRegex(ValueError, 'private path'):
                check_files([image])
