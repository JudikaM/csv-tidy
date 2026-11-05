"""Datakrit.exe: the Windows app starts the local interface, exactly like ``datakrit-ui``.

PyInstaller freezes this script (see datakrit.spec). The app has no command line: it calls
the same entry point as the ``datakrit-ui`` program, ``datakrit.ui.gui_main``, which opens
the browser, writes start-up problems to ``datakrit-ui-error.txt`` in the temporary folder,
and has a smoke mode for automated checks (the ``DATAKRIT_UI_URL_FILE`` environment
variable, see docs/CONFIGURATION.md).
"""

import sys

from datakrit.ui import gui_main

if __name__ == "__main__":
    sys.exit(gui_main())
