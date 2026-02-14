"""Small module to hold ephemeral application-level references.

Used to keep a reference to the active main window to avoid GC when
performing logout/login handover without creating globals on QApplication.
"""

main_window_ref = None
