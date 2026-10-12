from __future__ import annotations

import os
import random
import time
import urllib.error
import urllib.request

TARGET = os.environ.get("TARGET", "http://localhost:8000")

PATHS = ["/", "/healthz", "/work", "/work", "/work", "/work", "/slow", "/fail", "/nope"]


def hit(path: str) -> None:
    try:
        with urllib.request.urlopen(TARGET + path, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError:
        pass  # 404/500 from /fail and /nope are expected and are the point
    except Exception as exc:  # noqa: BLE001 - keep the loop alive no matter what
        print(f"[loadgen] {path}: {exc}", flush=True)
        time.sleep(2)


def main() -> None:
    print(f"[loadgen] target {TARGET}", flush=True)
    while True:
        hit(random.choice(PATHS))
        time.sleep(random.uniform(0.05, 0.5))


if __name__ == "__main__":
    main()