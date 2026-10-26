"""Builds the Claude artifact copy of the dashboard in build/artifact/: artifact.html (the page body, with the
same metadata as web/index.html) and postings/, the weekly postings files base64-encoded as .txt, since the
artifact host serves no .gz files. Each file stays well under the artifact's 16 MB per-file limit.
Run after build_dataset.py, then publish artifact.html with the postings/ files beside it."""
import base64
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build/artifact"


def main():
    index = (ROOT / "web/index.html").read_text()
    site = json.loads(gzip.decompress(base64.b64decode(json.loads(re.search(r'const EMBEDDED = ("[^"]+");', index).group(1)))))
    (OUT / "postings").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "postings").glob("*"):
        old.unlink()
    names = []
    for c in site["chunks"]:
        name = c + ".txt"
        (OUT / "postings" / name).write_bytes(base64.b64encode((ROOT / "web/postings" / c).read_bytes()))
        names.append(name)
    site["chunks"] = names
    payload = json.dumps(base64.b64encode(gzip.compress(json.dumps(site, separators=(",", ":"), ensure_ascii=False).encode(), 9)).decode())
    tpl = (ROOT / "web/template.html").read_text()
    (OUT / "artifact.html").write_text(tpl.replace("/*DATA*/null", payload))
    print(f"{OUT / 'artifact.html'} and {len(names)} weekly files")


if __name__ == "__main__":
    main()
