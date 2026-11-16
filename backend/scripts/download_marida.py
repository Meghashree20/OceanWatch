"""Download and verify the official MARIDA v1.0.0 archive from Zenodo."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

URL = "https://zenodo.org/records/5151941/files/MARIDA.zip?download=1"
EXPECTED_SIZE = 1_164_612_748
EXPECTED_MD5 = "9bf32266f6e3711c9dfa3699b856c76f"
DEFAULT_DESTINATION = Path(__file__).resolve().parents[1] / "data" / "MARIDA.zip"


def hash_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_range(start: int, end: int, part: Path) -> None:
    expected_length = end - start + 1
    if part.is_file() and part.stat().st_size == expected_length:
        return
    part.unlink(missing_ok=True)
    request = urllib.request.Request(URL, headers={
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
        "User-Agent": "OceanWatch-MARIDA-evaluator/1.0",
    })
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                if response.status != 206:
                    raise RuntimeError(f"Zenodo range request returned HTTP {response.status}, expected 206")
                expected_range = f"bytes {start}-{end}/{EXPECTED_SIZE}"
                if response.headers.get("Content-Range") != expected_range:
                    raise RuntimeError(f"Unexpected Content-Range: {response.headers.get('Content-Range')!r}")
                remaining = expected_length
                with part.open("wb") as target:
                    while remaining:
                        block = response.read(min(1024 * 1024, remaining))
                        if not block:
                            raise IOError("Zenodo connection ended before the requested range was complete")
                        target.write(block)
                        remaining -= len(block)
            return
        except Exception:
            part.unlink(missing_ok=True)
            if attempt == 4:
                raise
            time.sleep(attempt * 2)


def download(destination: Path, workers: int = 8) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == EXPECTED_SIZE:
        digest = hash_md5(destination)
        if digest != EXPECTED_MD5:
            raise ValueError(f"Existing archive MD5 mismatch: expected {EXPECTED_MD5}, found {digest}")
        return digest, EXPECTED_SIZE
    parts_dir = destination.with_name(f"{destination.name}.parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    plan_path = parts_dir / "ranges.json"
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("expected_size") != EXPECTED_SIZE:
            raise ValueError("Partial download plan has the wrong expected archive size")
        ranges = plan["ranges"]
    else:
        ranges: list[list[int]] = []
        prefix = 0
        if destination.is_file() and 0 < destination.stat().st_size < EXPECTED_SIZE:
            prefix = destination.stat().st_size
            shutil.move(str(destination), str(parts_dir / "part-000.bin"))
            ranges.append([0, prefix - 1])
        elif destination.exists():
            destination.unlink()
        remainder = EXPECTED_SIZE - prefix
        chunk_size = math.ceil(remainder / workers) if remainder else 0
        cursor = prefix
        while cursor < EXPECTED_SIZE:
            end = min(EXPECTED_SIZE - 1, cursor + chunk_size - 1)
            ranges.append([cursor, end])
            cursor = end + 1
        plan = {"url": URL, "expected_size": EXPECTED_SIZE, "expected_md5": EXPECTED_MD5, "ranges": ranges}
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    jobs = []
    for index, (start, end) in enumerate(ranges):
        part = parts_dir / f"part-{index:03d}.bin"
        if start == 0 and index == 0 and not part.exists() and destination.exists():
            raise RuntimeError("Unexpected partial archive state; refusing to overwrite it")
        if not (part.is_file() and part.stat().st_size == end - start + 1):
            jobs.append((start, end, part))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_range, start, end, part) for start, end, part in jobs]
        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            print(f"Downloaded {completed}/{len(jobs)} remaining byte ranges", flush=True)

    assembled = destination.with_suffix(destination.suffix + ".assembled")
    with assembled.open("wb") as output:
        for index, (start, end) in enumerate(ranges):
            part = parts_dir / f"part-{index:03d}.bin"
            if part.stat().st_size != end - start + 1:
                raise IOError(f"Incomplete archive range {start}-{end}")
            with part.open("rb") as source:
                shutil.copyfileobj(source, output, 1024 * 1024)
    size = assembled.stat().st_size
    if size != EXPECTED_SIZE:
        raise ValueError(f"Archive size mismatch: expected {EXPECTED_SIZE}, found {size}")
    md5 = hash_md5(assembled)
    if md5 != EXPECTED_MD5:
        assembled.unlink(missing_ok=True)
        raise ValueError(f"Archive MD5 mismatch: expected {EXPECTED_MD5}, found {md5}")
    assembled.replace(destination)
    shutil.rmtree(parts_dir)
    return md5, size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    args = parser.parse_args()
    digest, size = download(args.output, args.workers)
    print(f"Verified {args.output} ({size} bytes; MD5 {digest})")


if __name__ == "__main__":
    main()
