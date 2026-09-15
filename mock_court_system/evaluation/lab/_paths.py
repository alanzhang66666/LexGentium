"""Resolve mock_court_system root from evaluation/lab/*.py."""
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
EVAL_DIR = LAB_DIR.parent
PROJECT_ROOT = EVAL_DIR.parent
