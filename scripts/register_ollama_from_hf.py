#!/usr/bin/env python3
"""
Download the tuned APUSH GGUF from Hugging Face, register it in Ollama, and add it
as a tuned candidate in eval/models.json.

Usage:
  python3 scripts/register_ollama_from_hf.py
  python3 scripts/register_ollama_from_hf.py --repo rohanpalviela/qwen3-4b-apush-lora

If this stops at Hugging Face auth, run:
  hf auth login
then rerun this script.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout.strip():
        print(proc.stdout.rstrip())
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout)
    return proc


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise SystemExit(f"Missing `{name}`. Install it, then rerun this script.")


def check_hf_login() -> None:
    proc = run(["hf", "auth", "whoami"], check=False)
    if proc.returncode == 0:
        return
    raise SystemExit(
        "\nHugging Face is not logged in, or the token cannot be checked.\n"
        "Run this in your terminal, then rerun this script:\n\n"
        "  hf auth login\n"
    )


def download_repo(repo: str, local_dir: Path) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    run([
        "hf", "download", repo,
        "--include", "*.gguf",
        "--include", "Modelfile",
        "--local-dir", str(local_dir),
    ])


def find_gguf(local_dir: Path) -> Path:
    ggufs = sorted(local_dir.rglob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True)
    if not ggufs:
        raise SystemExit(
            f"\nNo .gguf file was found in {local_dir}.\n"
            "That means the Hugging Face repo still only has the LoRA adapter, or the GGUF "
            "was never uploaded from Colab.\n\n"
            "In Colab, rerun the GGUF export cell, then upload:\n"
            "  qwen3_4b_apush_gguf_gguf/qwen3-4b.Q4_K_M.gguf\n"
            "  qwen3_4b_apush_gguf_gguf/Modelfile\n"
        )
    return ggufs[0]


def build_local_modelfile(local_dir: Path, gguf: Path) -> Path:
    downloaded = local_dir / "Modelfile"
    out = local_dir / "Modelfile.local"
    rel_gguf = os.path.relpath(gguf, local_dir)

    if downloaded.exists():
        lines = downloaded.read_text(encoding="utf-8").splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if line.strip().startswith("FROM "):
                lines[i] = f"FROM ./{rel_gguf}"
                replaced = True
                break
        if not replaced:
            lines.insert(0, f"FROM ./{rel_gguf}")
        text = "\n".join(lines).rstrip() + "\n"
    else:
        text = (
            f"FROM ./{rel_gguf}\n"
            "PARAMETER num_ctx 4096\n"
            "PARAMETER temperature 0.7\n"
        )

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return out


def ollama_create(model_name: str, modelfile: Path) -> None:
    run(["ollama", "create", model_name, "-f", str(modelfile)])
    run(["ollama", "list"], check=False)


def update_eval_config(path: Path, model_name: str) -> None:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    candidates = cfg.setdefault("candidates", [])
    tuned = {
        "name": "qwen3-apush-tuned",
        "provider": "ollama",
        "model": model_name,
        "base_url": "http://localhost:11434",
        "think": False,
        "keep_alive": "15m",
        "format": "json",
        "max_tokens": 1536,
        "num_ctx": 4096,
    }

    for i, cand in enumerate(candidates):
        if cand.get("name") == tuned["name"] or cand.get("model") == model_name:
            candidates[i] = {**cand, **tuned}
            break
    else:
        candidates.append(tuned)

    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"updated {path.relative_to(ROOT)} with candidate `{model_name}`")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="rohanpalviela/qwen3-4b-apush-lora")
    ap.add_argument("--local-dir", default=str(ROOT / "models" / "qwen3-apush"))
    ap.add_argument("--model-name", default="qwen3-apush:latest")
    ap.add_argument("--eval-config", default=str(ROOT / "eval" / "models.json"))
    ap.add_argument("--skip-eval-config", action="store_true")
    args = ap.parse_args()

    require_tool("hf")
    require_tool("ollama")
    check_hf_login()

    local_dir = Path(args.local_dir).resolve()
    download_repo(args.repo, local_dir)
    gguf = find_gguf(local_dir)
    print(f"using GGUF: {gguf.relative_to(ROOT)} ({gguf.stat().st_size / (1024 ** 3):.2f} GiB)")

    modelfile = build_local_modelfile(local_dir, gguf)
    ollama_create(args.model_name, modelfile)

    if not args.skip_eval_config:
        update_eval_config(Path(args.eval_config).resolve(), args.model_name)

    print("\nDone. Quick smoke test:")
    print(f"  ollama run {args.model_name}")
    print("\nThen run the judged eval after exporting PROMPTLENS_API_KEY:")
    print("  python3 eval/harness.py --split EVAL_HELDOUT --runs 3 --n 6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
