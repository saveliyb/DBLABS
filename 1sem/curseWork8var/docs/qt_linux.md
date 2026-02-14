Qt on Ubuntu/Debian — missing xcb plugin

If running a PySide6 application on Ubuntu/Debian you may see an error like:

    qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
    Could not load the Qt platform plugin "xcb" ...

Solution (install minimal required package):

    sudo apt update
    sudo apt install -y libxcb-cursor0

If you still see problems, install a small bundle of common xcb/X11 dependencies used by Qt:

    sudo apt install -y libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0

Primary requirement: `libxcb-cursor0` — install it first.

Headless / CI note
-------------------
On servers or CI without an X server you can run Qt in offscreen/minimal mode (no GUI shown) by setting the environment variable:

    QT_QPA_PLATFORM=offscreen python -m app.main

or

    QT_QPA_PLATFORM=minimal python -m app.main

This avoids the xcb platform plugin requirement and is useful for smoke/import tests. Do not set this by default — only use it when running on headless systems.
