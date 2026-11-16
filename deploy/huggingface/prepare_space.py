"""Assemble the Hugging Face Space build context in deploy/huggingface/space/ (git-ignored).

Usage:  python deploy/huggingface/prepare_space.py
Then upload the folder to the Space (HfApi().upload_folder(..., repo_type="space")).
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "space"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "*.log", "*.db", "*.sqlite")

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
for f in ("Dockerfile", "README.md", "start.sh", "requirements-api.txt"):
    shutil.copy(HERE / f, OUT / f)
shutil.copytree(ROOT / "backend", OUT / "backend", ignore=SKIP)
shutil.copytree(ROOT / "reports", OUT / "reports", ignore=shutil.ignore_patterns("*.log"))
shutil.copytree(ROOT / "models", OUT / "models", ignore=SKIP)
(OUT / "frontend/public/assets").mkdir(parents=True)
shutil.copy(ROOT / "frontend/public/assets/editions.json", OUT / "frontend/public/assets/editions.json")
# start.sh must keep Unix line endings inside the Linux container
(OUT / "start.sh").write_bytes((OUT / "start.sh").read_bytes().replace(b"\r\n", b"\n"))
size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
print(f"Space context ready: {OUT}  ({size / 2**20:.1f} MB, {sum(1 for p in OUT.rglob('*') if p.is_file())} files)")
