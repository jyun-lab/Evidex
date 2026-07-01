import atexit
import os
import tempfile

_LEDGER_DIR = tempfile.TemporaryDirectory(prefix="evidex-tests-")
os.environ["EVIDEX_HOME"] = _LEDGER_DIR.name
atexit.register(_LEDGER_DIR.cleanup)

from evidex.core import config  # noqa: E402

config.set_base_dir(_LEDGER_DIR.name)
