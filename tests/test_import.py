"""Rahmentest: Paket ist importierbar, Einstiegspunkte laufen."""

import importlib

import pytest

import donstv_studio


def test_package_importable():
    assert donstv_studio.__version__


@pytest.mark.parametrize("sub", ["core", "overlays", "bot", "ui"])
def test_subpackages_importable(sub):
    importlib.import_module(f"donstv_studio.{sub}")


@pytest.mark.parametrize(
    ("module", "name"),
    [("donstv_studio.ui.main", "donstv-studio")],
)
def test_entrypoints_print_start_message(module, name, capsys):
    assert importlib.import_module(module).main() == 0
    assert name in capsys.readouterr().out
