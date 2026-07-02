import atexit
import os
import tempfile

_LEDGER_DIR = tempfile.TemporaryDirectory(prefix="evidex-tests-")
os.environ["EVIDEX_HOME"] = _LEDGER_DIR.name
atexit.register(_LEDGER_DIR.cleanup)

from evidex.core import config  # noqa: E402

config.set_base_dir(_LEDGER_DIR.name)


def reset_tk_style_singletons():
    """ttkbootstrap のグローバル状態を破棄する。

    ttkbootstrap.Style はプロセス内シングルトンで、最初に作られた Tk root に
    紐づく。テストが root を作り直すと、Style が破棄済みの root を参照し続け、
    以後の ttk ウィジェット生成が「application has been destroyed」で失敗する。
    Tk root を作る/破棄するテストは、この関数を setUp と tearDown で呼ぶこと。
    """
    try:
        from ttkbootstrap.style import Style
        from ttkbootstrap.publisher import Publisher

        Style.instance = None
        Publisher.clear_subscribers()
    except Exception:
        pass
