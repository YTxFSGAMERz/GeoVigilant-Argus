import sys
import os

# Ensure the root project directory is in the sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Expose app for Vercel WSGI runner
# WSGI entrypoint
app = app
