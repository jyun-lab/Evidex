"""Windows-specific window identity and icon helpers."""

import os
import struct
import sys
from pathlib import Path


def app_icon_candidates():
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "evidex" / "assets" / "evidex.ico")
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "evidex.ico")
    return candidates


def find_app_icon():
    return next((path for path in app_icon_candidates() if path.is_file()), None)


def read_ico_sizes(path):
    """Return the square image sizes declared by an ICO directory."""
    with Path(path).open("rb") as handle:
        header = handle.read(6)
        if len(header) != 6:
            raise ValueError("ICO header is truncated")
        reserved, image_type, count = struct.unpack("<HHH", header)
        if reserved != 0 or image_type != 1 or count < 1:
            raise ValueError("Invalid ICO header")

        sizes = set()
        for _ in range(count):
            entry = handle.read(16)
            if len(entry) != 16:
                raise ValueError("ICO directory is truncated")
            width, height = entry[0], entry[1]
            width = 256 if width == 0 else width
            height = 256 if height == 0 else height
            if width == height:
                sizes.add(width)
        return sizes


def _apply_win32_icons(window, icon_path):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.SendMessageW.restype = ctypes.c_ssize_t

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    GA_ROOT = 2
    SM_CXICON, SM_CYICON = 11, 12
    SM_CXSMICON, SM_CYSMICON = 49, 50

    hwnd = wintypes.HWND(window.winfo_id())
    root_hwnd = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
    path = os.fspath(icon_path)

    big = user32.LoadImageW(
        None,
        path,
        IMAGE_ICON,
        user32.GetSystemMetrics(SM_CXICON),
        user32.GetSystemMetrics(SM_CYICON),
        LR_LOADFROMFILE,
    )
    small = user32.LoadImageW(
        None,
        path,
        IMAGE_ICON,
        user32.GetSystemMetrics(SM_CXSMICON),
        user32.GetSystemMetrics(SM_CYSMICON),
        LR_LOADFROMFILE,
    )
    if not big or not small:
        raise ctypes.WinError(ctypes.get_last_error())

    user32.SendMessageW(root_hwnd, WM_SETICON, ICON_BIG, big)
    user32.SendMessageW(root_hwnd, WM_SETICON, ICON_SMALL, small)
    window._win_icon_handles = (big, small)
    return True


def apply_window_icon(window, icon_path=None):
    """Apply the application icon to Tk and the Windows taskbar window."""
    path = Path(icon_path) if icon_path else find_app_icon()
    result = {
        "path": os.fspath(path) if path else "",
        "tk_current": False,
        "tk_default": False,
        "tk_photo": False,
        "win32": False,
        "errors": [],
    }
    if path is None:
        result["errors"].append("icon asset not found")
        return result

    try:
        window.iconbitmap(os.fspath(path))
        result["tk_current"] = True
    except Exception as error:
        result["errors"].append(f"iconbitmap current: {error}")

    try:
        window.iconbitmap(default=os.fspath(path))
        result["tk_default"] = True
    except Exception as error:
        result["errors"].append(f"iconbitmap default: {error}")

    try:
        from PIL import Image, ImageTk

        source = Image.open(path)
        sizes = source.info.get("sizes", {(256, 256)})
        photos = []
        for size in ((256, 256), (48, 48), (32, 32), (16, 16)):
            if size not in sizes:
                continue
            image = source.ico.getimage(size) if hasattr(source, "ico") else source.copy()
            photos.append(ImageTk.PhotoImage(image.convert("RGBA"), master=window))
        if photos:
            window.iconphoto(True, *photos)
            window._app_icon_photos = photos
            result["tk_photo"] = True
    except Exception as error:
        result["errors"].append(f"iconphoto: {error}")

    if sys.platform == "win32":
        try:
            window.update_idletasks()
            result["win32"] = _apply_win32_icons(window, path)
        except Exception as error:
            result["errors"].append(f"WM_SETICON: {error}")

    return result


def release_window_icons(window):
    handles = getattr(window, "_win_icon_handles", ())
    if not handles or sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DestroyIcon.restype = wintypes.BOOL
        for handle in set(handles):
            if handle:
                user32.DestroyIcon(handle)
    finally:
        window._win_icon_handles = ()
