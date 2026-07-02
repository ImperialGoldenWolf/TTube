# Makefile for TTube Development

.PHONY: help install install-dev clean test lint format build uninstall run

help:
	@echo "TTube Development Commands"
	@echo "============================"
	@echo "make install       - Install TTube and dependencies"
	@echo "make install-dev   - Install with dev tools (pyinstaller, pytest, etc.)"
	@echo "make run          - Run TTube"
	@echo "make test         - Run tests (if available)"
	@echo "make lint         - Run code linting (flake8)"
	@echo "make format       - Format code (black)"
	@echo "make build        - Build standalone executable"
	@echo "make clean        - Clean build artifacts"
	@echo "make uninstall    - Uninstall TTube"

install:
	@echo "[*] Installing TTube..."
	python install_app.py

install-dev:
	@echo "[*] Installing TTube with dev tools..."
	python -m pip install -e ".[dev]"

run:
	@echo "[*] Starting TTube..."
	python -m ttube

test:
	@echo "[*] Running tests..."
	python -m pytest -v

lint:
	@echo "[*] Linting code..."
	python -m flake8 ttube.py ttube_stream.py ttube_youtube.py --max-line-length=120

format:
	@echo "[*] Formatting code..."
	python -m black ttube.py ttube_stream.py ttube_youtube.py

build:
	@echo "[*] Building standalone executable..."
	python -m pyinstaller ttube.spec
	@echo "[+] Build complete! Output in: dist/ttube/"

clean:
	@echo "[*] Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info __pycache__ .pytest_cache .coverage htmlcov
	rm -rf *.spec.bak
	@echo "[+] Clean complete"

uninstall:
	@echo "[!] Uninstalling TTube..."
	@echo "This will remove the .venv directory"
	rm -rf .venv
	@echo "[+] TTube uninstalled"

.DEFAULT_GOAL := help
