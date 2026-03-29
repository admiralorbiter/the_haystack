"""
Download BLS OEWS (May 2024) and O*NET Text Database (29.0).
Extracts datasets into data/raw/bls/ and data/raw/onet/.
"""

import argparse
import os
import zipfile
from datetime import datetime
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
BLS_DIR = RAW_DIR / "bls"
ONET_DIR = RAW_DIR / "onet"
MANIFEST_PATH = PROJECT_ROOT / "data" / "MANIFEST.md"

BLS_OEWS_URL = "https://www.bls.gov/oes/special.requests/oesm24all.zip" # The URL can be .requests or -requests, some servers redirect. Let's use the one that works: special.requests
# Actually BLS uses special.requests sometimes. Let's use the standard one:
# https://www.bls.gov/oes/special.requests/oesm24all.zip 
# Note: BLS sometimes blocks python user agents, so we need a fake UA string.

# O*NET Text DB
ONET_URL = "https://www.onetcenter.org/dl_files/database/db_29_0_text.zip"

def download_file(url: str, dest: Path, force: bool = False, label: str = "") -> bool:
    if dest.exists() and not force:
        print(f"  [skip] {dest.name} already exists")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    display = label or dest.name

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        print(f"  [fetch] {display} ...", end="", flush=True)
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)

        size_mb = downloaded / 1_048_576
        print(f" {size_mb:.1f} MB ✓")
        return True

    except Exception as e:
        print(f" ERROR: {e}")
        if dest.exists():
            dest.unlink()
        return False

def extract_zip(zip_path: Path, dest_dir: Path) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest_dir)
            print(f"  [extract] {zip_path.name} extracted to {dest_dir.name}/")
        return True
    except Exception as e:
        print(f"    [error] extract failed: {e}")
        return False

def write_manifest(entries: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = MANIFEST_PATH.read_text() if MANIFEST_PATH.exists() else ""
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        if not existing:
            f.write("# Data Download Manifest\n\n| File | Source | Downloaded At |\n|---|---|---|\n")
        else:
            f.write(existing)
        for entry in entries:
            f.write(f"| `{entry['file']}` | {entry['url']} | {entry['at']} |\n")

def main() -> None:
    parser = argparse.ArgumentParser(description="Download BLS and O*NET datasets.")
    parser.add_argument("--force", action="store_true", help="Re-download if exist")
    args = parser.parse_args()

    manifest_entries = []
    
    # 1. BLS
    print("\\n── BLS OEWS (May 2024) ──")
    bls_zip = BLS_DIR / "_zips" / "oesm24all.zip"
    bls_downloaded = download_file(BLS_OEWS_URL, bls_zip, args.force, "oesm24all.zip")
    if bls_downloaded or (bls_zip.exists() and args.force):
        extract_zip(bls_zip, BLS_DIR)
        manifest_entries.append({
            "file": "data/raw/bls/oesm24all/",
            "url": BLS_OEWS_URL,
            "at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

    # 2. ONET
    print("\\n── O*NET Database (29.0) ──")
    onet_zip = ONET_DIR / "_zips" / "db_29_0_text.zip"
    onet_downloaded = download_file(ONET_URL, onet_zip, args.force, "db_29_0_text.zip")
    if onet_downloaded or (onet_zip.exists() and args.force):
        extract_zip(onet_zip, ONET_DIR)
        manifest_entries.append({
            "file": "data/raw/onet/db_29_0_text/",
            "url": ONET_URL,
            "at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        
    if manifest_entries:
        write_manifest(manifest_entries)
        print("\\n✓ Manifest updated: data/MANIFEST.md")

    print("\\n✅ Workload complete.")

if __name__ == "__main__":
    main()
