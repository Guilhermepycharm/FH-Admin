from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fh_admin_tui.config import AppConfig
from fh_admin_tui.save_ops import NodeSaveCodec


class RealCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js nao esta instalado neste ambiente")

    def test_bundled_codec_script_has_valid_javascript_syntax(self) -> None:
        codec_script = AppConfig.from_env({}).codec_script

        result = subprocess.run(
            ["node", "--check", str(codec_script)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_node_save_codec_round_trip_with_controlled_lz_module(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-codec-real-") as temp_dir:
            root = Path(temp_dir)
            lz_string = root / "lz-string.js"
            source = root / "source.json"
            encoded = root / "encoded.rpgsave"
            decoded = root / "decoded.json"
            payload = '{"party":{"_items":{"1":2}},"note":"codec fixture"}'
            lz_string.write_text(
                "module.exports = {\n"
                "  compressToBase64(value) { return Buffer.from(value, 'utf8').toString('base64'); },\n"
                "  decompressFromBase64(value) { return Buffer.from(value, 'base64').toString('utf8'); }\n"
                "};\n",
                encoding="utf-8",
            )
            source.write_text(payload, encoding="utf-8")
            codec = NodeSaveCodec(AppConfig.from_env({}).codec_script, lz_string)

            codec.encode(source, encoded)
            codec.decode(encoded, decoded)

            self.assertEqual(decoded.read_text(encoding="utf-8"), payload)
