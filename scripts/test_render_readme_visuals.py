"""Regression checks for the deterministic bilingual README visual renderer."""

import importlib.util
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, __version__ as PILLOW_VERSION


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "render_readme_visuals.py"
EXPECTED_RENDER_SHA256 = {
    "readme-harness.en.png": "8ad852262f517f17ed2d7c9f31a2997ff85208c672ffe23dd193328eb6408551",
    "readme-harness.zh-TW.png": "b23ee287565c7cd2dedfe4f95c305c040cb4b6ca9703f23a0df94e7be0be2fae",
}
CANONICAL_RENDER_ENV = "FABLE_CANONICAL_RENDER"
_spec = importlib.util.spec_from_file_location("render_readme_visuals", SCRIPT)
renderer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(renderer)


def test_v4_source_art_renders_bilingual_readme_outputs():
    assert renderer.ART.name == "harness-core-image4.png"
    assert renderer.ART.is_file()
    original_assets, original_art = renderer.ASSETS, renderer.ART
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        source = workspace / renderer.ART.name
        shutil.copy2(renderer.ART, source)
        renderer.ASSETS, renderer.ART = workspace, source
        try:
            for language, expected_name in (
                    ("en", "readme-harness.en.png"),
                    ("zh-TW", "readme-harness.zh-TW.png")):
                output = renderer.render(language)
                assert output.name == expected_name
                with Image.open(output) as image:
                    assert image.size == (renderer.WIDTH, renderer.HEIGHT)
                    assert image.mode == "RGB"
                committed = original_assets / expected_name
                assert hashlib.sha256(committed.read_bytes()).hexdigest() == EXPECTED_RENDER_SHA256[expected_name]
                if os.environ.get(CANONICAL_RENDER_ENV) == "1":
                    assert os.name == "nt"
                    assert PILLOW_VERSION == "11.1.0"
                    # Pixel equality is the renderer contract.  PNG byte
                    # streams may vary across Pillow releases despite an
                    # identical rendered image and font stack.
                    with Image.open(output) as rendered, Image.open(committed) as expected:
                        assert rendered.tobytes() == expected.tobytes()
        finally:
            renderer.ASSETS, renderer.ART = original_assets, original_art


if __name__ == "__main__":
    test_v4_source_art_renders_bilingual_readme_outputs()
    print("ok test_v4_source_art_renders_bilingual_readme_outputs")
