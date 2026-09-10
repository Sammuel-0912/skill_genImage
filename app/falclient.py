# -*- coding: utf-8 -*-
"""FAL API 呼叫層：組 payload、送 queue、輪詢、下載、寫入 metadata。"""

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from . import config

TZ = timezone(timedelta(hours=8))
QUEUE = "https://queue.fal.run"
POLL_SECONDS = 2
MAX_WAIT = 900  # 15 分鐘


class FalError(Exception):
    pass


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _request(url, key, payload=None, timeout=120):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    req.add_header("Authorization", f"Key {key}")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        try:
            parsed = json.loads(detail)
            detail = parsed.get("detail") or parsed.get("message") or detail
            if isinstance(detail, list):
                detail = "; ".join(
                    f"{'.'.join(str(x) for x in d.get('loc', []))}: {d.get('msg', '')}"
                    if isinstance(d, dict) else str(d)
                    for d in detail
                )
        except Exception:
            pass
        raise FalError(f"HTTP {e.code} — {detail}")
    except urllib.error.URLError as e:
        raise FalError(f"連線失敗：{e.reason}")


def build_payload(model, values: dict, prompt: str, refs: list) -> dict:
    """依模型的參數表組出 API payload。空字串的參數會被略過。"""
    payload = {"prompt": prompt}

    for spec in model.params:
        key = spec["key"]
        val = values.get(key, spec.get("default"))
        if val is None or val == "":
            continue
        if spec.get("type") == "int":
            try:
                val = int(val)
            except (TypeError, ValueError):
                continue
        if refs and spec.get("ref_locked") is not None:
            val = spec["ref_locked"]
        payload[key] = val

    if refs:
        uris = [data_uri(Path(r)) for r in refs]
        if model.ref_multi:
            payload[model.ref_field] = uris[: model.ref_max]
        else:
            payload[model.ref_field] = uris[0]

    return payload


def next_path(out_dir: Path, model_id: str, ext: str) -> Path:
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M")
    n = 1
    while True:
        suffix = "" if n == 1 else f"-{n}"
        cand = out_dir / f"{model_id}-{stamp}{suffix}.{ext}"
        if not cand.exists():
            return cand
        n += 1


def write_meta(path: Path, meta: dict) -> None:
    target = config.META_DIR / (path.name + ".json")
    try:
        target.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def read_meta(path: Path) -> dict:
    target = config.META_DIR / (path.name + ".json")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}


def delete_meta(path: Path) -> None:
    target = config.META_DIR / (path.name + ".json")
    try:
        target.unlink()
    except OSError:
        pass


class GenerateWorker(QObject):
    """在背景執行緒跑一次生成。"""

    status = Signal(str)          # 進度文字
    done = Signal(list, dict)     # [Path, ...], meta
    failed = Signal(str)

    def __init__(self, model, values, prompt, refs, key, out_dir):
        super().__init__()
        self.model = model
        self.values = dict(values)
        self.prompt = prompt
        self.refs = list(refs)
        self.key = key
        self.out_dir = Path(out_dir)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            paths, meta = self._run()
        except FalError as e:
            self.failed.emit(str(e))
        except Exception as e:                       # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")
        else:
            if not self._cancelled:
                self.done.emit(paths, meta)

    # -------------------------------------------------------------- internal

    def _run(self):
        if not self.key:
            raise FalError("尚未設定 FAL 金鑰。請到「偏好設定」貼上你的金鑰。")

        endpoint = self.model.endpoint(bool(self.refs))
        if not endpoint:
            raise FalError(f"模型 {self.model.label} 沒有對應的接口。")

        self.status.emit("正在上傳提示詞…")
        payload = build_payload(self.model, self.values, self.prompt, self.refs)

        job = _request(f"{QUEUE}/{endpoint}", self.key, payload, timeout=180)
        status_url = job.get("status_url")
        response_url = job.get("response_url")

        if status_url:
            waited = 0
            while True:
                if self._cancelled:
                    return [], {}
                st = _request(status_url, self.key)
                state = st.get("status")
                if state == "COMPLETED":
                    break
                if state in ("FAILED", "ERROR", "CANCELLED"):
                    raise FalError(json.dumps(st, ensure_ascii=False)[:400])
                qp = st.get("queue_position")
                if state == "IN_QUEUE" and qp is not None:
                    self.status.emit(f"排隊中（第 {qp} 位）")
                else:
                    self.status.emit(f"生成中… {waited}s")
                time.sleep(POLL_SECONDS)
                waited += POLL_SECONDS
                if waited > MAX_WAIT:
                    raise FalError("等待逾時（15 分鐘）。可降低解析度或張數再試。")
            result = _request(response_url, self.key, timeout=180)
        else:
            result = job

        return self._save(result, endpoint, payload)

    def _save(self, result: dict, endpoint: str, payload: dict):
        files = []
        if isinstance(result.get("images"), list):
            files = result["images"]
        elif isinstance(result.get("video"), dict):
            files = [result["video"]]
        if not files:
            raise FalError(f"沒有回傳檔案：{json.dumps(result, ensure_ascii=False)[:300]}")

        meta = {
            "model": self.model.label,
            "model_id": self.model.id,
            "mode": self.model.mode,
            "endpoint": endpoint,
            "prompt": self.prompt,
            "params": {k: v for k, v in payload.items()
                       if k not in ("prompt", "image_url", "image_urls")},
            "references": [Path(r).name for r in self.refs],
            "created": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            "description": result.get("description", ""),
        }

        self.status.emit("下載中…")
        saved = []
        for f in files:
            url = f.get("url")
            if not url:
                continue
            name = f.get("file_name") or ""
            if "." in name:
                ext = name.rsplit(".", 1)[1].lower()
            else:
                ct = f.get("content_type") or ""
                ext = "mp4" if "video" in ct else (payload.get("output_format") or "png")
            dest = next_path(self.out_dir, self.model.id, ext)
            with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as r:
                dest.write_bytes(r.read())
            write_meta(dest, meta)
            saved.append(dest)

        if not saved:
            raise FalError("回傳的檔案沒有可下載的網址。")
        return saved, meta


def start_worker(worker: GenerateWorker) -> QThread:
    """把 worker 丟到新的 QThread 執行，回傳 thread（呼叫端要留住參考）。"""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    return thread
