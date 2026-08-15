"""Serve one photo-card exhibition and synchronize real local workflow state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


SCRIPTS = Path(__file__).resolve().parent
MAX_BODY = 64 * 1024
STATUS_WEIGHTS = {
    "awaiting-high-resolution-render": 8,
    "queued": 8,
    "rendering": 34,
    "high-resolution-rendering": 34,
    "generated": 58,
    "rendered": 58,
    "composing": 72,
    "qa": 86,
    "quality-assurance": 86,
    "complete": 96,
    "packaged": 100,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def selected_ids(delivery: Path) -> list[str]:
    lock = load_json(delivery / "selection.lock.json")
    items = lock.get("items") or []
    if items:
        return [item["preset"] for item in items]
    primary = lock.get("primary_preset")
    return [primary] if primary else []


def packing_payload(delivery: Path) -> dict:
    take_home = delivery / "take-home"
    status = load_json(take_home / "packing-status.json")
    items = status.get("items") or []
    stage = status.get("stage", "not-started")
    if stage == "ready-for-pickup":
        return {
            "stage": "complete",
            "percent": 100,
            "message": "高清作品已完成装裱与打包，可以取件。",
            "path": str(take_home.resolve()),
            "receipt": "take-home/index.html",
            "archive": "take-home/laplacelajiang-collection.zip",
            "items": items,
        }
    if not items:
        return {
            "stage": "not-started",
            "percent": 0,
            "message": "尚未提交高清制作",
            "path": str(take_home.resolve()),
            "items": [],
        }
    weights = [STATUS_WEIGHTS.get(item.get("status", ""), 8) for item in items]
    percent = sum(weights) / len(weights)
    failed = [item for item in items if item.get("status") == "failed"]
    if failed:
        message = f"{len(failed)} 幅作品需要重新处理；已完成部分会保留。"
        view_stage = "failed"
    elif percent >= 96:
        message = "高清作品已生成，正在核对取件清单与压缩包。"
        view_stage = "packaging"
    elif percent >= 72:
        message = "正在进行版式合成、展签整理与质量检查。"
        view_stage = "rendering"
    elif percent >= 34:
        message = "正在逐幅生成高清母版；已完成结果会立即写入取件目录。"
        view_stage = "rendering"
    else:
        message = "收藏单已锁定，等待高清制作任务接管。"
        view_stage = "queued"
    return {
        "stage": view_stage,
        "percent": round(percent, 1),
        "message": message,
        "path": str(take_home.resolve()),
        "items": items,
    }


class ExhibitionState:
    def __init__(self, delivery: Path, idle_timeout: int) -> None:
        self.delivery = delivery
        self.idle_timeout = idle_timeout
        self.last_heartbeat = time.monotonic()
        self.server: ThreadingHTTPServer | None = None
        self.lock = threading.Lock()

    def heartbeat(self) -> None:
        with self.lock:
            self.last_heartbeat = time.monotonic()

    def idle_seconds(self) -> float:
        with self.lock:
            return time.monotonic() - self.last_heartbeat

    def status(self) -> dict:
        session = load_json(self.delivery / "session.json")
        return {
            "ok": True,
            "server_time": now(),
            "session_stage": session.get("stage", "unknown"),
            "selected": selected_ids(self.delivery),
            "packing": packing_payload(self.delivery),
        }


class ExhibitionHandler(SimpleHTTPRequestHandler):
    server_version = "LaplaceLajiangGallery/4.0"

    def __init__(self, *args: object, state: ExhibitionState, **kwargs: object):
        self.state = state
        super().__init__(*args, directory=str(state.delivery), **kwargs)

    def log_message(self, fmt: str, *args: object) -> None:
        if self.path.startswith("/api/heartbeat"):
            return
        super().log_message(fmt, *args)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if self.path.endswith((".html", ".json", ".js", ".css")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path: str):  # type: ignore[no-untyped-def]
        self.send_error(HTTPStatus.FORBIDDEN, "Directory listing is disabled")
        return None

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length_value = self.headers.get("Content-Length", "0")
        try:
            length = int(length_value)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > MAX_BODY:
            raise ValueError("request body must be between 1 byte and 64 KiB")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/status":
            self.state.heartbeat()
            self.send_json(self.state.status())
            return
        if route == "/api/heartbeat":
            self.state.heartbeat()
            self.send_json({"ok": True})
            return
        if route == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/previews/style-gallery.html")
            self.end_headers()
            return
        self.state.heartbeat()
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route != "/api/selection":
            self.send_json({"error": "unknown API route"}, 404)
            return
        self.state.heartbeat()
        try:
            payload = self.read_json()
            presets = payload.get("presets")
            if not isinstance(presets, list) or not 1 <= len(presets) <= 6:
                raise ValueError("presets must contain 1–6 artwork IDs")
            if any(not isinstance(value, str) for value in presets):
                raise ValueError("every preset ID must be a string")
            if len(set(presets)) != len(presets):
                raise ValueError("selected artwork IDs must be unique")
            command = [
                sys.executable,
                str(SCRIPTS / "manage_session.py"),
                "select",
                str(self.state.delivery),
                "--append",
            ]
            for preset in presets:
                command.extend(("--preset", preset))
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode:
                reason = (result.stderr or result.stdout).strip()
                raise ValueError(reason or "selection could not be locked")
            response = self.state.status()
            response["message"] = result.stdout.strip()
            self.send_json(response)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:  # pragma: no cover - final defensive boundary
            self.send_json({"error": f"local service error: {exc}"}, 500)


def monitor_idle(state: ExhibitionState) -> None:
    while state.server:
        time.sleep(15)
        if state.idle_seconds() >= state.idle_timeout:
            print(
                f"INFO: no gallery heartbeat for {state.idle_timeout}s; "
                "stopping local service"
            )
            state.server.shutdown()
            return


def serve(
    delivery: Path,
    host: str,
    port: int,
    open_browser: bool,
    idle_timeout: int,
) -> int:
    delivery = delivery.resolve()
    gallery = delivery / "previews" / "style-gallery.html"
    if not gallery.is_file():
        raise SystemExit(f"gallery is missing: {gallery}")
    if host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("gallery server only binds to localhost")
    state = ExhibitionState(delivery, idle_timeout)
    handler = partial(ExhibitionHandler, state=state)
    server = ThreadingHTTPServer((host, port), handler)
    state.server = server
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/previews/style-gallery.html"
    save_json(
        delivery / "previews" / "gallery-server.json",
        {
            "schema_version": 1,
            "url": url,
            "host": "127.0.0.1",
            "port": actual_port,
            "started_at": now(),
            "idle_timeout_seconds": idle_timeout,
        },
    )
    print(f"PASS: exhibition service -> {url}")
    print(f"PASS: take-home path -> {(delivery / 'take-home').resolve()}")
    if open_browser:
        threading.Timer(0.45, lambda: webbrowser.open(url)).start()
    monitor = threading.Thread(target=monitor_idle, args=(state,), daemon=True)
    monitor.start()
    try:
        server.serve_forever(poll_interval=0.35)
    except KeyboardInterrupt:
        print("INFO: exhibition service stopped")
    finally:
        state.server = None
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--idle-timeout", type=int, default=300)
    args = parser.parse_args()
    return serve(
        args.delivery,
        args.host,
        args.port,
        args.open,
        max(90, args.idle_timeout),
    )


if __name__ == "__main__":
    raise SystemExit(main())
