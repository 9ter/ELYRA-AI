import base64
import binascii
import io
import json
import os
import struct
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elyra import imagegen
from elyra.domain import validate_scenes


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x80\x40\xc0")) + chunk(b"IEND", b"")


class ImageGenTest(unittest.TestCase):
    def test_prompt_always_adds_adult_tags_and_safety_negative(self):
        positive, negative = imagegen.build_prompt("long silver hair", "lying in bed", "blurry")
        self.assertTrue(positive.startswith("masterpiece, best quality, adult, mature, long silver hair"))
        self.assertIn("loli", negative)
        self.assertTrue(negative.endswith("blurry"))

    def test_minor_terms_rejected(self):
        for text in ("loli, bed", "a Teen girl", "schoolgirl uniform", "CHILD"):
            with self.assertRaises(imagegen.ImageGenError):
                imagegen.build_prompt("", text)
        with self.assertRaises(imagegen.ImageGenError):
            imagegen.build_prompt("underage", "bed")

    def test_empty_scene_prompt_rejected(self):
        with self.assertRaises(imagegen.ImageGenError):
            imagegen.build_prompt("silver hair", "  ")

    def test_only_loopback_forge(self):
        with mock.patch.dict(os.environ, {"FORGE_URL": "http://example.com:7860"}):
            with self.assertRaises(imagegen.ImageGenError):
                imagegen.base_url()
        with mock.patch.dict(os.environ, {"FORGE_URL": "http://127.0.0.1:7861/"}):
            self.assertEqual(imagegen.base_url(), "http://127.0.0.1:7861")

    def test_generate_validates_returned_image(self):
        response = io.BytesIO(json.dumps({"images": [base64.b64encode(png()).decode()]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            media = imagegen.generate("silver hair", "lying in bed")
        body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(body["hr_additional_modules"], [])  # Forge Neo hires fix needs this
        self.assertEqual((body["steps"], body["scheduler"], body["hr_upscaler"], body["hr_scale"]), (32, "Karras", "Latent", 2))
        self.assertEqual(media["mime"], "image/png")
        bad = io.BytesIO(json.dumps({"images": [base64.b64encode(b"<svg/>" * 10).decode()]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=bad):
            with self.assertRaises(ValueError):
                imagegen.generate("silver hair", "lying in bed")

    def test_settings_validated_and_merged_over_defaults(self):
        saved = imagegen.validate_settings({"steps": 20, "cfg_scale": 7.5, "checkpoint": " other.safetensors ", "junk": 1})
        self.assertEqual((saved["steps"], saved["cfg_scale"], saved["checkpoint"]), (20, 7.5, "other.safetensors"))
        self.assertEqual(saved["scheduler"], "Karras")
        self.assertNotIn("junk", saved)
        for bad in ({"steps": 0}, {"steps": 2.5}, {"steps": True}, {"width": 513}, {"denoising_strength": 1.5},
                    {"enable_hr": "yes"}, {"sampler_name": 3}, {"width": 2048, "height": 2048, "hr_scale": 2.5}):
            with self.assertRaises(imagegen.ImageGenError):
                imagegen.validate_settings(bad)
        self.assertEqual(imagegen.validate_settings({"width": 2048, "hr_scale": 4, "enable_hr": False})["width"], 2048)

    def test_generate_uses_saved_settings_and_checkpoint(self):
        response = io.BytesIO(json.dumps({"images": [base64.b64encode(png()).decode()]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            imagegen.generate("silver hair", "bed", settings={"steps": 12, "checkpoint": "anime.safetensors [abc]", "enable_hr": False})
        body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual((body["steps"], body["enable_hr"]), (12, False))
        self.assertEqual(body["override_settings"], {"sd_model_checkpoint": "anime.safetensors [abc]"})
        self.assertNotIn("checkpoint", body)

    def test_generated_images_allow_4mb_but_uploads_keep_2mb(self):
        from elyra.media import validate_image
        payload = {"data": base64.b64encode(png()).decode() + "A" * (3 * 1024 * 1024)}  # ~3 MB encoded
        with self.assertRaisesRegex(ValueError, "2 MB"):
            validate_image(payload)
        with self.assertRaises(ValueError) as caught:
            validate_image(payload, imagegen.MAX_GENERATED_BYTES)
        self.assertNotIn("2 MB", str(caught.exception))  # passes the size gate, fails later as invalid data

    def test_loras_added_as_tags_with_trigger_words(self):
        positive, _ = imagegen.build_prompt("silver hair", "lying in bed", loras=[
            {"name": "yoonseoah_v1", "weight": 0.8, "trigger": "yoonseoah"}, {"name": "detail tweaker", "weight": -0.5}])
        self.assertTrue(positive.startswith("masterpiece, best quality, adult, mature, yoonseoah, silver hair"))
        self.assertTrue(positive.endswith("<lora:yoonseoah_v1:0.8> <lora:detail tweaker:-0.5>"))

    def test_lora_validation(self):
        for bad in ([{"name": "x>evil"}], [{"name": "a:b"}], [{"name": ""}], [{"name": "ok", "weight": 3}],
                    [{"name": "ok", "weight": True}], [{"name": "ok", "trigger": "loli"}], [{"name": f"l{i}"} for i in range(6)], "x"):
            with self.assertRaises(imagegen.ImageGenError):
                imagegen.validate_loras(bad)
        self.assertEqual(imagegen.validate_loras([{"name": " a ", "weight": 1}]), [{"name": "a", "weight": 1.0, "trigger": ""}])

    def test_character_stores_loras(self):
        from elyra.domain import validate_character
        character = validate_character({"name": "ซออา", "age": 27, "description": "x", "personality": "y", "greeting": "z",
                                        "image_loras": [{"name": "yoonseoah_v1", "weight": 0.7, "trigger": "yoonseoah"}]})
        self.assertEqual(character["image_loras"], [{"name": "yoonseoah_v1", "weight": 0.7, "trigger": "yoonseoah"}])

    def test_negative_prompts_stored_and_appended(self):
        from elyra.domain import validate_character
        scene = validate_scenes([{"media_id": "a" * 64, "description": "นอนบนเตียง", "negative": " glasses "}])[0]
        self.assertEqual(scene["negative"], "glasses")
        character = validate_character({"name": "ซออา", "age": 27, "description": "x", "personality": "y", "greeting": "z",
                                        "image_negative": "short hair, tattoo"})
        self.assertEqual(character["image_negative"], "short hair, tattoo")
        _, negative = imagegen.build_prompt("", "bed", "short hair, glasses")
        self.assertTrue(negative.startswith(imagegen.SAFETY_NEGATIVE))  # safety terms always stay first
        self.assertTrue(negative.endswith("short hair, glasses"))
        with self.assertRaises(imagegen.ImageGenError):
            imagegen.build_prompt("", "bed", "x" * 2001)

    def test_options_asks_forge_to_rescan_checkpoints_and_loras(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            url = request if isinstance(request, str) else request.full_url
            calls.append((getattr(request, "method", "GET") if not isinstance(request, str) else "GET", url.split("/sdapi/v1/")[1]))
            data = {"sd-models": [{"title": "new.safetensors"}], "options": {"sd_model_checkpoint": "new.safetensors"},
                    "samplers": [{"name": "Euler"}], "schedulers": [{"name": "karras", "label": "Karras"}],
                    "latent-upscale-modes": [{"name": "Latent"}], "upscalers": [{"name": "None"}], "loras": []}
            return io.BytesIO(json.dumps(data.get(url.split("/sdapi/v1/")[1], {})).encode())
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = imagegen.options()
        posts = [path for method, path in calls if method == "POST"]
        self.assertEqual(posts, ["refresh-checkpoints", "refresh-loras"])
        self.assertLess(calls.index(("POST", "refresh-checkpoints")), calls.index(("GET", "sd-models")))
        self.assertEqual(result["checkpoints"], ["new.safetensors"])

    def test_scene_prompt_field_kept(self):
        scene = validate_scenes([{"media_id": "a" * 64, "description": "นอนบนเตียง", "prompt": " lying in bed "}])[0]
        self.assertEqual(scene["prompt"], "lying in bed")
        with self.assertRaises(ValueError):
            validate_scenes([{"media_id": "a" * 64, "description": "นอนบนเตียง", "prompt": "x" * 1001}])


if __name__ == "__main__":
    unittest.main()
