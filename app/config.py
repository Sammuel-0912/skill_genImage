# -*- coding: utf-8 -*-
"""設定、路徑、模型表與成本估算。"""

import json
import os
import re
from pathlib import Path

APP_NAME = "FAL Studio"

# 專案根目錄 = app/ 的上一層
ROOT = Path(__file__).resolve().parent.parent
MODELS_FILE = ROOT / "models.json"
PRICING_FILE = ROOT / "pricing.json"
ENV_FILE = ROOT / ".env"
OUT_DIR = ROOT / "finished_file"
REF_DIR = ROOT / "referenced_image"
META_DIR = OUT_DIR / ".meta"

for d in (OUT_DIR, REF_DIR, META_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- .env 金鑰

def read_key() -> str:
    """從 .env 或環境變數讀 FAL_KEY。"""
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "FAL_KEY":
                    v = v.strip().strip('"').strip("'")
                    if v:
                        return v
        except OSError:
            pass
    return os.environ.get("FAL_KEY", "").strip()


def write_key(key: str) -> None:
    """把 FAL_KEY 寫回 .env，保留檔案裡其他內容。"""
    key = key.strip()
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    replaced = False
    out = []
    for line in lines:
        if re.match(r"\s*FAL_KEY\s*=", line):
            if not replaced:
                out.append(f"FAL_KEY={key}")
                replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"FAL_KEY={key}")
    ENV_FILE.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def mask_key(key: str) -> str:
    if not key:
        return "（未設定）"
    if len(key) <= 12:
        return key[:2] + "…"
    return f"{key[:6]}…{key[-4:]}"


# ---------------------------------------------------------------- 模型表

def _load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


class Model:
    """models.json 裡的一筆模型。"""

    def __init__(self, raw: dict, mode: str):
        self.raw = raw
        self.mode = mode                      # "image" / "video"
        self.id = raw["id"]
        self.label = raw.get("label", self.id)
        self.vendor = raw.get("vendor", "")
        self.endpoints = raw.get("endpoints", {})
        self.ref_field = raw.get("ref_field", "image_urls")
        self.ref_multi = bool(raw.get("ref_multi", True))
        self.ref_max = int(raw.get("ref_max", 1))
        self.params = raw.get("params", [])

    def endpoint(self, has_ref: bool) -> str:
        if has_ref and self.endpoints.get("ref"):
            return self.endpoints["ref"]
        return self.endpoints.get("text", "")

    def defaults(self) -> dict:
        return {p["key"]: p.get("default") for p in self.params}

    def param(self, key: str):
        for p in self.params:
            if p["key"] == key:
                return p
        return None


def load_models() -> dict:
    raw = _load_json(MODELS_FILE, {"image": [], "video": []})
    return {
        "image": [Model(m, "image") for m in raw.get("image", [])],
        "video": [Model(m, "video") for m in raw.get("video", [])],
    }


def load_pricing() -> dict:
    return _load_json(PRICING_FILE, {})


# ---------------------------------------------------------------- 成本估算

def _seconds_from(values: dict, pricing: dict) -> float:
    d = values.get("duration", "")
    m = re.search(r"\d+(\.\d+)?", str(d))
    if m:
        return float(m.group())
    return float(pricing.get("defaults", {}).get("video_seconds_when_auto", 5))


def estimate_cost(model: "Model", values: dict, pricing: dict):
    """回傳 (金額, 是否為估計值)。找不到價目時回 (None, False)。"""
    table = pricing.get(model.mode, {}).get(model.id)
    if not table:
        return None, False

    price = float(table.get("base", 0.0))
    for key, mapping in (table.get("multipliers") or {}).items():
        v = str(values.get(key, ""))
        if v in mapping:
            price *= float(mapping[v])

    if table.get("unit") == "per_second":
        price *= _seconds_from(values, pricing)
    else:
        try:
            price *= max(1, int(values.get("num_images", 1) or 1))
        except (TypeError, ValueError):
            pass
    return price, True


def format_cost(amount) -> str:
    if amount is None:
        return "—"
    if amount < 0.01:
        return f"~${amount:.4f}"
    if amount < 1:
        return f"~${amount:.3f}".rstrip("0").rstrip(".")
    return f"~${amount:.2f}"
