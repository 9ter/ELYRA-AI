"""Local image generation through a Stable Diffusion WebUI (A1111 / Forge) API on loopback only."""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .media import validate_image

QUALITY = "masterpiece, best quality"
ADULT = "adult, mature"
# Always appended, whatever the user writes: generated characters must read as adults.
SAFETY_NEGATIVE = "child, children, kid, loli, shota, young, underage, teen, toddler"
DEFAULT_NEGATIVE = "lowres, bad anatomy, bad hands, extra fingers, missing fingers, text, watermark, signature, blurry"
BLOCKED = re.compile(r"\b(child|children|kid|kids|loli|lolicon|shota|shotacon|underage|minor|toddler|teen|teenager|"
                     r"preteen|schoolgirl|elementary)\b", re.I)


class ImageGenError(ValueError):
    pass


def base_url():
    url = os.environ.get("FORGE_URL", "http://127.0.0.1:7860").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1") \
            or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ImageGenError("อนุญาตเฉพาะ Stable Diffusion บนเครื่องนี้ (localhost)")
    return url


MAX_LORAS = 5
LORA_NAME = re.compile(r"[^<>:\r\n]{1,120}")  # anything that cannot break out of the <lora:name:weight> tag


def validate_loras(loras):
    """Character-bound LoRAs: [{name, weight -2..2, trigger words}]. Applied as <lora:name:weight> in the prompt."""
    if not isinstance(loras, list) or len(loras) > MAX_LORAS:
        raise ImageGenError(f"ผูก LoRA ได้ไม่เกิน {MAX_LORAS} ตัว")
    result = []
    for lora in loras:
        if not isinstance(lora, dict):
            raise ImageGenError("ข้อมูล LoRA ไม่ถูกต้อง")
        name, weight, trigger = lora.get("name", ""), lora.get("weight", 1), lora.get("trigger", "")
        if not isinstance(name, str) or not LORA_NAME.fullmatch(name.strip()):
            raise ImageGenError("ชื่อ LoRA ไม่ถูกต้อง (ห้ามมี < > :)")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not -2 <= weight <= 2:
            raise ImageGenError("น้ำหนัก LoRA ต้องอยู่ระหว่าง -2 ถึง 2")
        if not isinstance(trigger, str) or len(trigger) > 200 or BLOCKED.search(trigger):
            raise ImageGenError("คำเรียก LoRA ต้องไม่เกิน 200 ตัวอักษรและไม่สื่อถึงผู้เยาว์")
        result.append({"name": name.strip(), "weight": round(float(weight), 2), "trigger": trigger.strip()})
    return result


def build_prompt(character_prompt, scene_prompt, negative="", loras=()):
    for text in (character_prompt, scene_prompt):
        if not isinstance(text, str) or len(text) > 1000:
            raise ImageGenError("prompt ต้องเป็นข้อความไม่เกิน 1,000 ตัวอักษร")
        if BLOCKED.search(text):
            raise ImageGenError("prompt ต้องไม่มีคำที่สื่อถึงผู้เยาว์ ตัวละครทุกตัวต้องเป็นผู้ใหญ่")
    if not scene_prompt.strip():
        raise ImageGenError("กรุณากรอก prompt ภาษาอังกฤษของฉากก่อนสร้างภาพ")
    if not isinstance(negative, str) or len(negative) > 2000:
        raise ImageGenError("negative prompt ต้องเป็นข้อความไม่เกิน 2,000 ตัวอักษร")
    loras = validate_loras(list(loras))
    triggers = ", ".join(lora["trigger"] for lora in loras if lora["trigger"])
    tags = " ".join(f'<lora:{lora["name"]}:{lora["weight"]:g}>' for lora in loras)
    positive = ", ".join(part for part in (QUALITY, ADULT, triggers, character_prompt.strip(), scene_prompt.strip()) if part)
    negative = ", ".join(part for part in (SAFETY_NEGATIVE, DEFAULT_NEGATIVE, (negative or "").strip()) if part)
    return (f"{positive} {tags}" if tags else positive), negative


# Defaults match the user's own Forge txt2img settings (512x768 → hires 2x = 1024x1536, ~25 s/image on their GPU).
# Users can change these in Settings; they are stored as settings["image"]. checkpoint "" = whatever Forge has loaded.
DEFAULTS = {"checkpoint": "", "sampler_name": "DPM++ 2M", "scheduler": "Karras", "steps": 32, "cfg_scale": 6.0,
            "width": 512, "height": 768, "enable_hr": True, "hr_scale": 2.0, "hr_upscaler": "Latent",
            "hr_second_pass_steps": 32, "denoising_strength": 0.6, "hr_cfg": 6.0}
NUMBERS = {"steps": (int, 1, 150), "cfg_scale": (float, 1, 30), "width": (int, 256, 2048), "height": (int, 256, 2048),
           "hr_scale": (float, 1, 4), "hr_second_pass_steps": (int, 0, 150), "denoising_strength": (float, 0, 1),
           "hr_cfg": (float, 1, 30)}
TEXTS = {"checkpoint": 300, "sampler_name": 80, "scheduler": 80, "hr_upscaler": 80}
MAX_GENERATED_BYTES = 4 * 1024 * 1024  # 1024x1536 PNGs are ~1.6 MB; uploads keep the 2 MB limit
MAX_OUTPUT_SIDE = 4096  # media.validate_image rejects larger images


def validate_settings(data):
    """Merge user settings over DEFAULTS with strict types and ranges; unknown keys are dropped."""
    if not isinstance(data, dict):
        raise ImageGenError("การตั้งค่าสร้างภาพไม่ถูกต้อง")
    result = dict(DEFAULTS)
    for key, maximum in TEXTS.items():
        value = data.get(key, result[key])
        if not isinstance(value, str) or len(value) > maximum:
            raise ImageGenError(f"ค่า {key} ไม่ถูกต้อง")
        result[key] = value.strip()
    for key, (kind, low, high) in NUMBERS.items():
        value = data.get(key, result[key])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high \
                or (kind is int and value != int(value)):
            raise ImageGenError(f"ค่า {key} ต้องอยู่ระหว่าง {low}–{high}")
        result[key] = kind(value)
    if result["width"] % 8 or result["height"] % 8:
        raise ImageGenError("ความกว้างและความสูงต้องหารด้วย 8 ลงตัว")
    enable_hr = data.get("enable_hr", result["enable_hr"])
    if not isinstance(enable_hr, bool):
        raise ImageGenError("ค่า Hires fix ไม่ถูกต้อง")
    result["enable_hr"] = enable_hr
    scale = result["hr_scale"] if enable_hr else 1
    if max(result["width"], result["height"]) * scale > MAX_OUTPUT_SIDE:
        raise ImageGenError(f"ขนาดภาพสุดท้ายต้องไม่เกิน {MAX_OUTPUT_SIDE} px ต่อด้าน ลดขนาดหรือค่า Upscale")
    return result


def _get(path, timeout=15):
    try:
        with urllib.request.urlopen(base_url() + path, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ImageGenError("เชื่อมต่อ Stable Diffusion ไม่ได้ ตรวจว่า Forge เปิดอยู่ที่พอร์ต 7860 พร้อม --api") from None


def options():
    """Choices offered by the running Forge instance, for the Settings page."""
    upscalers = [item["name"] for item in _get("/sdapi/v1/latent-upscale-modes")] + \
                [item["name"] for item in _get("/sdapi/v1/upscalers") if item.get("name") != "None"]
    # Forge only rescans model folders when asked, so files added after it started never appeared in the lists.
    for path in ("/sdapi/v1/refresh-checkpoints", "/sdapi/v1/refresh-loras"):
        try:  # harmless if an endpoint is missing
            urllib.request.urlopen(urllib.request.Request(base_url() + path, method="POST"), timeout=60).close()
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    return {"loras": sorted(item["name"] for item in (_get("/sdapi/v1/loras") or []) if item.get("name")),
            "checkpoints": [item["title"] for item in _get("/sdapi/v1/sd-models")],
            "current_checkpoint": _get("/sdapi/v1/options").get("sd_model_checkpoint", ""),
            "samplers": [item["name"] for item in _get("/sdapi/v1/samplers")],
            "schedulers": [item.get("label") or item["name"] for item in _get("/sdapi/v1/schedulers")],
            "upscalers": upscalers}


def generate(character_prompt, scene_prompt, negative="", settings=None, loras=(), timeout=900):
    """Return a validated media dict ({id, mime, data}) for one image using the saved generation settings."""
    positive, negative = build_prompt(character_prompt, scene_prompt, negative, loras)
    config = validate_settings(settings or {})
    body = {"prompt": positive, "negative_prompt": negative, "seed": -1,
            **{key: value for key, value in config.items() if key != "checkpoint"},
            "hr_additional_modules": []}  # Forge Neo's hires fix fails with a TypeError when this is missing
    if config["checkpoint"]:
        # Switching checkpoints makes the first image slower while Forge loads the model.
        body["override_settings"] = {"sd_model_checkpoint": config["checkpoint"]}
        body["override_settings_restore_afterwards"] = False
    request = urllib.request.Request(base_url() + "/sdapi/v1/txt2img", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            images = json.load(response).get("images") or []
    except urllib.error.HTTPError as exc:
        raise ImageGenError(f"Stable Diffusion สร้างภาพไม่สำเร็จ (HTTP {exc.code}) ตรวจว่าเปิด --api และมีโมเดลโหลดอยู่") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ImageGenError("เชื่อมต่อ Stable Diffusion ไม่ได้ ตรวจว่า Forge เปิดอยู่ที่พอร์ต 7860 พร้อม --api") from None
    if not images:
        raise ImageGenError("Stable Diffusion ไม่ส่งภาพกลับมา")
    try:
        base64.b64decode(images[0], validate=True)
    except ValueError:
        raise ImageGenError("ข้อมูลภาพจาก Stable Diffusion ไม่ถูกต้อง") from None
    return validate_image({"data": images[0]}, MAX_GENERATED_BYTES)
