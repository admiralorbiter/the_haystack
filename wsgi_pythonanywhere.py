# ============================================================================
# PythonAnywhere WSGI configuration for The Haystack
# ============================================================================
# Paste this file's contents into:
#   /var/www/haystack-jlane_pythonanywhere_com_wsgi.py
# on PythonAnywhere, adjusting the path below to match your home directory.
# ============================================================================

import sys
import os

# -- Project path ------------------------------------------------------------
# Make sure Python can find the project and its dependencies.
path = "/home/jlane/the_haystack"
if path not in sys.path:
    sys.path.insert(0, path)

# -- Environment variables ---------------------------------------------------
# Option A (recommended): set SECRET_KEY and DATABASE_URL in the
#   PythonAnywhere dashboard → "Web" tab → "Environment variables" section.
#
# Option B: load a .env file (install python-dotenv first):
#   pip install python-dotenv
# from dotenv import load_dotenv
# load_dotenv(os.path.join(path, ".env"))

# -- Application factory -----------------------------------------------------
# IMPORTANT: use "production" — NOT "development".
# "development" enables debug mode which must NEVER run in production.
from app import create_app  # noqa: E402

application = create_app("production")
