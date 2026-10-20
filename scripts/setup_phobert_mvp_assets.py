"""Download the pinned official VnCoreNLP JAR and RDRSegmenter assets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "runs/phobert_mvp_news_100_v1/vncorenlp"
REPOSITORY_COMMIT = "62bbc58fe5d113c898eae112656be97dcf50b3a0"
ASSETS = {
    "VnCoreNLP-1.2.jar": "9e2811cdbc2ddfc71d04be5dc36e185c88dcd1ad4d5d69e4ff2e1369dccf7793",
    "models/wordsegmenter/vi-vocab": "0a47c5b55bbce163029d37730a67b9479740388695c29c106c112b815613eaa5",
    "models/wordsegmenter/wordsegmenter.rdr": "9e62f96bd93e37a24f364238e8d8ae986fa5dad6dbc9f4eae622ab3651b7fa06",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    for relative, expected_hash in ASSETS.items():
        target = ASSET_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256(target) == expected_hash:
            print(f"verified {relative}")
            continue
        url = f"https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/{REPOSITORY_COMMIT}/{relative}"
        temporary = target.with_suffix(target.suffix + ".download")
        with urlopen(url, timeout=180) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        actual_hash = sha256(temporary)
        if actual_hash != expected_hash:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"SHA-256 mismatch for {relative}: {actual_hash}")
        temporary.replace(target)
        print(f"downloaded and verified {relative}")


if __name__ == "__main__":
    main()
