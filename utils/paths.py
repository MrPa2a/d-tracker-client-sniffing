import sys
import os

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS for --onefile
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            # For --onedir, resources are typically in _internal
            # But let's check if it's in the root or _internal
            exe_dir = os.path.dirname(sys.executable)
            internal_dir = os.path.join(exe_dir, '_internal')
            if os.path.exists(os.path.join(internal_dir, relative_path)):
                base_path = internal_dir
            else:
                base_path = exe_dir
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
