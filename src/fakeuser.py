from __future__ import annotations

import os
import random
import time
import urllib.error
import urllib.request

TARGET = os.environ.get("TARGET")

PATHS = ["/", "/healthz", "/work", "/work", "/slow", "/work", "/fail", "/work", "/nope"]


def hit(path: str) -> None:
    try:
        with urllib.request.urlopen(TARGET + path, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError:
        pass  # 404/500 
    except Exception as exc:
        time.sleep(2)


def main() -> None:
    while True:
        hit(random.choice(PATHS))
        time.sleep(random.uniform(0.05, 0.5))


if __name__ == "__main__":
    main()