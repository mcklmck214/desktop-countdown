#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具 · 通用工具函数（Beta 0.4）
路径定位、日期解析、剩余天数计算、开机自启动。
"""

import os
import re
import sys
from datetime import date, datetime, timedelta


def home_dir():
    return os.path.expanduser("~")


def app_dir():
    """程序所在目录：打包后为 exe 所在目录，源码运行时为脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """资源目录：打包后为 _MEIPASS，源码运行时为脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_dir())
    return app_dir()


def _launch_command():
    """开机自启动命令：打包后直接指向 exe；源码运行时优先用 pythonw 避免弹黑窗。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    if sys.platform.startswith("win"):
        quiet = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(quiet):
            exe = quiet
    # sys.argv[0] 是入口脚本，避免注册成 utils.py
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}"'


def today():
    return datetime.now().date()


# --------------------------------------------------------------------------- #
# Windows 系统集成：DPI 感知、窗口阴影、多显示器
# --------------------------------------------------------------------------- #
def enable_dpi_awareness():
    """开启高分屏 DPI 感知，避免 4K / 150% 缩放下界面被系统拉伸变糊。

    优先逐显示器 V2（跨不同 DPI 的屏幕也不会被位图拉伸），
    其次系统级 DPI 感知，最后退回旧 API。必须在创建任何 Tk 窗口之前调用。
    """
    if not sys.platform.startswith("win"):
        return False
    import ctypes
    user32 = ctypes.windll.user32
    try:
        # Win10 1703+：PER_MONITOR_AWARE_V2
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return True
    except Exception:
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(1) == 0:
            return True
    except Exception:
        pass
    try:
        if user32.SetProcessDPIAware():
            return True
    except Exception:
        pass
    try:
        # 以上都失败通常说明已被 manifest 设为感知，检查实际状态
        value = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(value))
        return value.value != 0
    except Exception:
        return False


def _window_hwnd(window):
    """取 Tk 窗口对应的真实 HWND（Tk 会多包一层 wrapper，优先取父窗口）。"""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        return hwnd or window.winfo_id()
    except Exception:
        return None


def enable_dwm_shadow(window):
    """给无边框窗口补回系统级阴影。

    做法与 Electron 的 frameless 窗口一致：把 DWM 边框向客户区延伸 1px，
    让系统重新绘制窗口阴影；对 -transparentcolor 的层叠窗口同样有效。
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        hwnd = _window_hwnd(window)
        if not hwnd:
            return False
        margins = MARGINS(1, 1, 1, 1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
            hwnd, ctypes.byref(margins))
        return True
    except Exception as exc:
        print("启用系统阴影失败:", exc, file=sys.stderr)
        return False


def enable_rounded_corners(window):
    """Windows 11：让无边框窗口使用系统圆角（旧系统静默失败）。"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        hwnd = _window_hwnd(window)
        if not hwnd:
            return False
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ok = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        return ok == 0
    except Exception:
        return False


def monitor_work_area(x, y):
    """返回距离 (x, y) 最近的显示器工作区 (left, top, right, bottom)。

    非 Windows 或调用失败返回 None。
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MONITOR_DEFAULTTONEAREST = 2
        point = wintypes.POINT(int(x), int(y))
        hmon = ctypes.windll.user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return None
        r = info.rcWork
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def clamp_to_work_area(x, y, w, h, fallback=None):
    """把窗口位置钳制到所在显示器的工作区内，支持副屏负坐标。

    fallback 为主屏尺寸 (sw, sh)，仅在拿不到显示器信息时使用。
    """
    area = monitor_work_area(x + w // 2, y + h // 2) or monitor_work_area(x, y)
    if area is None:
        if fallback:
            sw, sh = fallback
            area = (0, 0, sw, sh)
        else:
            return (max(0, int(x)), max(0, int(y)))
    left, top, right, bottom = area
    max_x = max(left, right - w)
    max_y = max(top, bottom - h)
    return (max(left, min(int(x), max_x)), max(top, min(int(y), max_y)))


def parse_date_str(text):
    s = text.strip()
    if not s:
        raise ValueError("请输入日期")
    m = re.match(r"^(\d{4})\s*\D+\s*(\d{1,2})\s*\D+\s*(\d{1,2})\s*\D*$", s)
    if m is None:
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m is None:
        raise ValueError("日期格式应为 yyyy年mm月dd日")
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise ValueError("日期不存在，请检查年月日")


def item_remaining(item, t=None):
    t = t or today()
    if item.get("mode") == "date":
        d = date.fromisoformat(item["date"])
    else:
        base = date.fromisoformat(item.get("base") or t.isoformat())
        d = base + timedelta(days=int(item.get("days", 0)))
    return (d - t).days


def set_auto_start(enable):
    if sys.platform.startswith("win"):
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            name = "DesktopCountdown"
            if enable:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as exc:
            print("设置开机自启动失败:", exc, file=sys.stderr)
    elif sys.platform == "darwin":
        pass
    else:
        autostart = os.path.join(home_dir(), ".config", "autostart")
        try:
            os.makedirs(autostart, exist_ok=True)
        except OSError:
            return
        desktop = os.path.join(autostart, "desktop_countdown.desktop")
        if enable:
            try:
                with open(desktop, "w", encoding="utf-8") as f:
                    f.write(
                        "[Desktop Entry]\n"
                        "Type=Application\n"
                        "Name=无名小工具\n"
                        f"Exec={_launch_command()}\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            except OSError:
                pass
        else:
            try:
                os.remove(desktop)
            except OSError:
                pass
