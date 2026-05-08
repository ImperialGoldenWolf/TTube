from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.check_call(cmd, cwd=str(cwd))


def _looks_like_venv(path: Path) -> bool:
    return (path / "pyvenv.cfg").exists()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="install.py",
        description="Create a virtualenv and install TTube (plus dependencies).",
    )
    parser.add_argument(
        "--venv",
        default=".venv",
        help="Virtualenv directory to create/use (default: .venv)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the virtualenv (only if it looks like a venv)",
    )
    parser.add_argument(
        "--editable",
        action="store_true",
        default=True,
        help="Install the project in editable mode (default: true)",
    )
    parser.add_argument(
        "--no-editable",
        action="store_false",
        dest="editable",
        help="Install the project non-editable (pip install .)",
    )
    parser.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="Skip upgrading pip/setuptools/wheel inside the venv",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run TTube after installation",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent
    venv_dir = (repo_root / args.venv).resolve()

    if args.recreate and venv_dir.exists():
        if not _looks_like_venv(venv_dir):
            raise SystemExit(f"Refusing to delete '{venv_dir}': not a virtualenv (missing pyvenv.cfg).")
        shutil.rmtree(venv_dir)

    if not venv_dir.exists():
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(str(venv_dir))

    py = _venv_python(venv_dir)
    if not py.exists():
        raise SystemExit(f"Virtualenv python not found at: {py}")

    if not args.skip_pip_upgrade:
        _run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=repo_root)

    install_cmd = [str(py), "-m", "pip", "install"]
    if args.editable:
        install_cmd += ["-e", "."]
    else:
        install_cmd += ["."]
    _run(install_cmd, cwd=repo_root)

    run_cmd = [str(py), "-m", "ttube"]

    print("\nInstalled TTube into:", venv_dir)
    print("Run:")
    print("  ", " ".join(run_cmd))

    if args.run:
        _run(run_cmd, cwd=repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
