"""Centralized selectors for the dashboard.

This filename overlaps Python's standard-library ``selectors`` module. Re-export
its API so libraries such as ``subprocess`` continue to work from this directory.
"""

import importlib.util
import sysconfig
from pathlib import Path

_stdlib_path = Path(sysconfig.get_path("stdlib")) / "selectors.py"
_stdlib_spec = importlib.util.spec_from_file_location("_stdlib_selectors", _stdlib_path)
if _stdlib_spec is None or _stdlib_spec.loader is None:
    raise ImportError("Could not load the standard-library selectors module")
_stdlib_selectors = importlib.util.module_from_spec(_stdlib_spec)
_stdlib_spec.loader.exec_module(_stdlib_selectors)

for _name in dir(_stdlib_selectors):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_stdlib_selectors, _name)

EMAIL_INPUT = "input[type='email'], input[name='email'], input[name='username']"
PASSWORD_INPUT = "input[type='password'], input[name='password']"
LOGIN_BUTTON = "button[type='submit']"
LOGIN_BUTTON_NAME = "Let's Go!"
LOGIN_ERROR = "[role='alert'], .alert-danger, .error, .error-message"
MOBILE_DAY_CARD = "xpath=ancestor::div[contains(@class, 'overflow-hidden')][1]"
MOBILE_LESSON_CARD = "div.space-y-2.p-3 > div.rounded-2xl"
