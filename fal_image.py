#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fal_image.py — 透過 FAL AI 平台生成/編輯圖片。

支援接口 (endpoints)
--------------------
  nano-banana-2        文生圖   fal-ai/nano-banana-2
  nano-banana-2/edit   圖生圖   fal-ai/nano-banana-2/edit
  gpt-image-2          文生圖   openai/gpt-image-2
  gpt-image-2/edit     圖生圖   openai/gpt-image-2/edit

給了 --ref 就自動改用該模型的 /edit 接口。

用法
----
  python fal_image.py --prompt "一隻在頂樓看夕陽的貓"
  python fal_image.py --model gpt-image-2 --prompt "扁平風格的登入頁" --aspect 1:1 --n 2
  python fal_image.py --prompt "把這個角色放進雨夜街景" --ref character_2.png

預設：模型 nano-banana-2、比例 16:9、1 張。
金鑰讀自 <專案>/.env 的 FAL_KEY（或環境變數 FAL_KEY）。
參考圖預設從 <專案>/參考圖 讀取，成品寫到 <專案>/完成檔，
檔名為「模型名稱-年月日-時分.png」（同分鐘內第 2 張起加 -2、-3）。
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))  # Asia/Taipei
QUEUE = "https://queue.fal.run"

MODELS = {
    "nano-banana-2": {
        "text": "fal-ai/nano-banana-2",
        "edit": "fal-ai/nano-banana-2/edit",
    },
    "gpt-image-2": {
        "text": "openai/gpt-image-2",
        "edit": "openai/gpt-image-2/edit",
    },
}

# gpt-image-2 只吃 image_size 列舉，這裡把常用比例對應過去
GPT_SIZE = {
    "16:9": "landscape_16_9",
    "9:16": "portrait_16_9",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
    "1:1": "square_hd",
    "auto": "auto",
}
# 列舉之外的比例改用自訂尺寸（寬高需為 16 的倍數，總像素 655360–8294400）
GPT_CUSTOM = {
    "21:9": (2016, 864),
    "3:2": (1536, 1024),
    "2:3": (1024, 1536),
    "5:4": (1280, 1024),
    "4:5": (1024, 1280),
}

NB_ASPECTS = ["auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1",
              "4:5", "3:4", "2:3", "9:16", "4:1", "1:4", "8:1", "1:8"]


def die(msg):
    print(f"錯誤：{msg}", file=sys.stderr)
    sys.exit(1)


def load_key(project: Path) -> str:
    env_file = project / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "FAL_KEY":
                v = v.strip().strip('"').strip("'")
                if v:
                    return v
    key = os.environ.get("FAL_KEY", "").strip()
    if key:
        return key
    die(f"找不到 FAL_KEY。請在 {env_file} 寫入 FAL_KEY=你的金鑰")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def resolve_ref(name: str, project: Path) -> Path:
    p = Path(name)
    candidates = [p, project / "參考圖" / p.name, project / p]
    for c in candidates:
        if c.is_file():
            return c
    die(f"找不到參考圖 {name}（已找過 參考圖/ 資料夾）")


def http(url, key, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Key {key}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:1500]
        die(f"FAL API {e.code}：{body}")
    except urllib.error.URLError as e:
        die(f"連線失敗：{e.reason}")


def run(endpoint, payload, key, verbose=True):
    job = http(f"{QUEUE}/{endpoint}", key, payload)
    status_url = job.get("status_url")
    response_url = job.get("response_url")
    if not status_url:
        return job  # 少數情況直接回結果
    waited = 0
    while True:
        st = http(status_url, key)
        s = st.get("status")
        if s == "COMPLETED":
            break
        if s in ("FAILED", "ERROR", "CANCELLED"):
            die(f"任務失敗：{json.dumps(st, ensure_ascii=False)[:800]}")
        if verbose and waited % 10 == 0:
            print(f"  ...排隊中（{waited}s，{s}）", file=sys.stderr)
        time.sleep(2)
        waited += 2
        if waited > 900:
            die("等待逾時（15 分鐘）")
    return http(response_url, key)


def download(url: str, dest: Path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())


def build_payload(model, mode, args, refs):
    p = {"prompt": args.prompt, "num_images": args.n, "output_format": "png"}
    if args.seed is not None:
        p["seed"] = args.seed
    if refs:
        p["image_urls"] = refs

    if model == "nano-banana-2":
        if args.aspect not in NB_ASPECTS:
            die(f"nano-banana-2 不支援比例 {args.aspect}，可用：{', '.join(NB_ASPECTS)}")
        p["aspect_ratio"] = args.aspect
        p["resolution"] = args.resolution
        if args.system_prompt:
            p["system_prompt"] = args.system_prompt
        if args.thinking:
            p["thinking_level"] = args.thinking
        if args.web_search:
            p["enable_web_search"] = True
    else:  # gpt-image-2
        if args.aspect in GPT_SIZE:
            p["image_size"] = GPT_SIZE[args.aspect]
        elif args.aspect in GPT_CUSTOM:
            w, h = GPT_CUSTOM[args.aspect]
            p["image_size"] = {"width": w, "height": h}
        else:
            die(f"gpt-image-2 不支援比例 {args.aspect}，"
                f"可用：{', '.join(list(GPT_SIZE) + list(GPT_CUSTOM))}")
        p["quality"] = args.quality
        p["background"] = args.background
        if args.mask:
            p["mask_url"] = data_uri(resolve_ref(args.mask, args.project))
    return p


def out_name(outdir: Path, model: str, idx: int, total: int) -> Path:
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M")
    base = f"{model}-{stamp}"
    n = idx + 1
    while True:
        suffix = "" if n == 1 else f"-{n}"
        cand = outdir / f"{base}{suffix}.png"
        if not cand.exists():
            return cand
        n += 1


def main():
    ap = argparse.ArgumentParser(description="透過 FAL AI 生成/編輯圖片")
    ap.add_argument("--prompt", required=True, help="提示詞")
    ap.add_argument("--model", default="nano-banana-2", choices=list(MODELS))
    ap.add_argument("--ref", nargs="*", default=[],
                    help="參考圖檔名（預設從 參考圖/ 資料夾找）；給了就走 /edit 接口")
    ap.add_argument("--aspect", default="16:9", help="寬高比，預設 16:9")
    ap.add_argument("--n", type=int, default=1, help="生成張數，預設 1")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--project", type=Path, default=Path(__file__).resolve().parent,
                    help="專案資料夾（含 .env、參考圖、完成檔），預設為腳本所在目錄")
    ap.add_argument("--outdir", type=Path, default=None, help="覆寫輸出資料夾")
    # nano-banana-2 專用
    ap.add_argument("--resolution", default="2K", choices=["0.5K", "1K", "2K", "4K"])
    ap.add_argument("--system-prompt", dest="system_prompt", default="")
    ap.add_argument("--thinking", default=None, choices=["minimal", "high"])
    ap.add_argument("--web-search", dest="web_search", action="store_true")
    # gpt-image-2 專用
    ap.add_argument("--quality", default="high", choices=["auto", "low", "medium", "high"])
    ap.add_argument("--background", default="auto", choices=["auto", "transparent", "opaque"])
    ap.add_argument("--mask", default=None, help="gpt-image-2/edit 的遮罩圖")
    args = ap.parse_args()

    project = args.project.resolve()
    key = load_key(project)
    outdir = (args.outdir or project / "完成檔").resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    mode = "edit" if args.ref else "text"
    endpoint = MODELS[args.model][mode]
    refs = [data_uri(resolve_ref(r, project)) for r in args.ref]

    payload = build_payload(args.model, mode, args, refs)
    print(f"接口：{endpoint}｜比例 {args.aspect}｜{args.n} 張"
          + (f"｜參考圖 {len(refs)} 張" if refs else ""), file=sys.stderr)

    result = run(endpoint, payload, key)
    images = result.get("images") or []
    if not images:
        die(f"沒有回傳圖片：{json.dumps(result, ensure_ascii=False)[:800]}")

    saved = []
    for i, img in enumerate(images):
        dest = out_name(outdir, args.model, i, len(images))
        download(img["url"], dest)
        saved.append(dest)
        print(f"已儲存：{dest}")

    if result.get("description"):
        print(f"模型說明：{result['description']}", file=sys.stderr)
    print(json.dumps([str(s) for s in saved], ensure_ascii=False))


if __name__ == "__main__":
    main()
