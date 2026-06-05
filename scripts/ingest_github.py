"""
Ingest GitHub repos into corpus/github/.

Clones (or updates) repos, extracts:
  - README.md (and any other .md docs)
  - git log (last 100 commits: hash, date, message)
  - File tree summary

Run: python scripts/ingest_github.py
"""

import os
import subprocess
import sys
from pathlib import Path

REPOS = [
    {
        "url": "https://github.com/Himeshxx04/rag-pipeline-optimizer",
        "name": "rag-pipeline-optimizer",
    },
    {
        "url": "https://github.com/Himeshxx04/mcp-artifact-store",
        "name": "mcp-artifact-store",
    },
]

GITHUB_DIR = Path("corpus/github")


def run(cmd: list, cwd=None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[warn] command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def clone_or_update(repo: dict) -> Path:
    dest = GITHUB_DIR / repo["name"]
    if (dest / ".git").exists():
        print(f"[github] Updating {repo['name']}...")
        run(["git", "pull", "--ff-only"], cwd=dest)
    else:
        print(f"[github] Cloning {repo['url']}...")
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth=200", repo["url"], str(dest)])
    return dest


def extract_readme(repo_dir: Path) -> str:
    for name in ["README.md", "readme.md", "README.rst", "README.txt"]:
        p = repo_dir / name
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
    return ""


def extract_git_log(repo_dir: Path, n: int = 100) -> str:
    log = run(
        ["git", "log", f"-{n}", "--pretty=format:%h %ad %s", "--date=short"],
        cwd=repo_dir,
    )
    return log


def extract_file_tree(repo_dir: Path) -> str:
    """Summarise the repo structure (top 2 levels, skip .git and node_modules)."""
    lines = []
    for p in sorted(repo_dir.rglob("*")):
        rel = p.relative_to(repo_dir)
        parts = rel.parts
        if any(part.startswith(".") or part in {"node_modules", "__pycache__", "venv", "env"} for part in parts):
            continue
        if len(parts) <= 2:
            indent = "  " * (len(parts) - 1)
            lines.append(f"{indent}{rel.name}{'/' if p.is_dir() else ''}")
    return "\n".join(lines[:80])  # cap at 80 lines


def extract_docs(repo_dir: Path) -> list[tuple[str, str]]:
    """Return [(filename, content)] for any .md files beyond the root README."""
    results = []
    for p in sorted(repo_dir.rglob("*.md")):
        rel = p.relative_to(repo_dir)
        if rel.name.lower() == "readme.md" and len(rel.parts) == 1:
            continue  # already extracted
        parts = rel.parts
        if any(part.startswith(".") or part in {"node_modules", "__pycache__"} for part in parts):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore").strip()
        if len(text) > 100:
            results.append((str(rel), text))
    return results


def process_repo(repo: dict):
    repo_dir = clone_or_update(repo)
    out_dir = GITHUB_DIR / repo["name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    readme = extract_readme(repo_dir)
    if readme:
        (out_dir / "README.md").write_text(readme, encoding="utf-8")
        print(f"  ✓ README ({len(readme)} chars)")

    git_log = extract_git_log(repo_dir)
    if git_log:
        (out_dir / "git_log.txt").write_text(git_log, encoding="utf-8")
        print(f"  ✓ git log ({git_log.count(chr(10))+1} commits)")

    file_tree = extract_file_tree(repo_dir)
    if file_tree:
        (out_dir / "file_tree.txt").write_text(file_tree, encoding="utf-8")
        print(f"  ✓ file tree")

    for fname, content in extract_docs(repo_dir):
        safe_name = fname.replace("/", "_").replace("\\", "_")
        (out_dir / safe_name).write_text(content, encoding="utf-8")
        print(f"  ✓ doc: {fname}")


def main():
    GITHUB_DIR.mkdir(parents=True, exist_ok=True)
    for repo in REPOS:
        print(f"\n── {repo['name']} ──")
        try:
            process_repo(repo)
        except Exception as e:
            print(f"  ERROR: {e}")
    print("\n[github] Done. Now rebuild the FAISS index:")
    print('  python -c "from persona.ingest import build_index; build_index(force=True)"')


if __name__ == "__main__":
    main()
