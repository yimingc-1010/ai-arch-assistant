"""Tests for lawrag.config helper functions."""

import pytest


def test_get_laws_dir_default(monkeypatch):
    monkeypatch.delenv("LAWRAG_LAWS_DIR", raising=False)
    from lawrag.config import get_laws_dir
    assert get_laws_dir() == "./data/laws"


def test_get_laws_dir_reads_env(monkeypatch):
    monkeypatch.setenv("LAWRAG_LAWS_DIR", "/custom/laws")
    from lawrag.config import get_laws_dir
    assert get_laws_dir() == "/custom/laws"
