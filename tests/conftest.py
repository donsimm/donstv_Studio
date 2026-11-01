import os

# Qt-Tests ohne Bildschirm (Debian-Laptop: X11, Tests: offscreen)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
