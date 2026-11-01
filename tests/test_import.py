"""Rahmentest: Paket ist importierbar, Einstiegspunkte laufen."""

import importlib

import pytest

import donstv_studio


def test_package_importable():
    assert donstv_studio.__version__


@pytest.mark.parametrize("sub", ["core", "overlays", "bot", "ui"])
def test_subpackages_importable(sub):
    importlib.import_module(f"donstv_studio.{sub}")


def test_ui_entrypoint_importable_without_qt():
    # Der Einstieg importiert Qt erst beim Start; ohne PyQt6 bleibt das Modul importierbar.
    assert callable(importlib.import_module("donstv_studio.ui.main").main)
