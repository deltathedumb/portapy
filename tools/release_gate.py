from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REQUIRED = {"windows": "portapy.dll", "linux": "libportapy.so"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    args = parser.parse_args()
    records = {}
    for platform, name in REQUIRED.items():
        path = args.dist / name
        if not path.is_file() or path.stat().st_size < 4096:
            raise SystemExit(f"missing or implausibly small native artifact: {path}")
        records[name] = {"platform": platform, "sha256": sha256(path), "size": path.stat().st_size}
    (args.dist / "checksums.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
