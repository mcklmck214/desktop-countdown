#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面透明倒计时  Beta 0.2.2
Python 3.12 + tkinter + pystray + Pillow
"""

print("请勿关闭这个窗口(^_^)")      #这行代码在以py文件的方式运行时显示

import json
import os
import re
import sys
import shutil
import threading
import webbrowser
import queue
import errno
import socket
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox, filedialog

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    pystray = None
    Image = None
    ImageDraw = None


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
APP_VERSION = "Beta 0.2.2"
MAX_DAYS = 1000
SINGLE_INSTANCE_PORT = 48291

BG_DARK = "#12161c"
BG_PANEL = "#1b2027"
FG_MAIN = "#e8eef5"
FG_SUB = "#8b9bab"
ACCENT = "#4fc3f7"
OVERDUE = "#ef5350"
ENTRY_BG = "#0e1218"
LINK_COLOR = "#5ec2ff"
TRANSPARENT_KEY = "#010203"
BTN_BG = "#2a323c"
BTN_HOVER = "#3a4550"
BTN_PRIMARY = "#2f6fb5"
BTN_PRIMARY_HOVER = "#3b82d1"

DEFAULT_COLORS = {
    "today": "#ffffff",
    "3": "#ef5350",
    "7": "#f06292",
    "30": "#ffca28",
    "365": "#42a5f5",
    "1000": "#ffffff",
}
RANGE_KEYS = ["today", "3", "7", "30", "365", "1000"]
RANGE_LABELS = {
    "today": "今天",
    "3": "3 天内",
    "7": "7 天内",
    "30": "30 天内",
    "365": "365 天内",
    "1000": "1000 天内",
}

BILI_URL = "https://space.bilibili.com/2061499488"
EMAIL = "mcklmck214@outlook.com"
QQ_FEEDBACK = ("823223052", "https://qm.qq.com/q/livvSfQFfG", "无名小工具反馈群")
QQ_CHAT = ("684287871", "https://qm.qq.com/q/1Q95hMYAxG", "无名小工具交流群")
QQ_COLLECT = ("136476657", "https://qm.qq.com/q/twudn725CU", "无名小工具征集群")

if sys.platform.startswith("win"):
    UI_FONT = "Microsoft YaHei UI"
elif sys.platform == "darwin":
    UI_FONT = "PingFang SC"
else:
    UI_FONT = "Noto Sans CJK SC"

WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def _home():
    return os.path.expanduser("~")


def _bootstrap_path():
    return os.path.join(_home(), ".desktop_countdown_dir.json")


def get_save_dir():
    bp = _bootstrap_path()
    if os.path.exists(bp):
        try:
            with open(bp, "r", encoding="utf-8") as f:
                d = json.load(f).get("save_dir")
            if d and os.path.isdir(d):
                return d
        except Exception:
            pass
    return _home()


def get_config_path():
    return os.path.join(get_save_dir(), ".desktop_countdown.json")


def set_save_dir(new_dir):
    old_path = get_config_path()
    new_path = os.path.join(new_dir, ".desktop_countdown.json")
    if os.path.abspath(old_path) != os.path.abspath(new_path):
        try:
            if os.path.exists(old_path) and not os.path.exists(new_path):
                shutil.copy2(old_path, new_path)
        except OSError:
            pass
    try:
        with open(_bootstrap_path(), "w", encoding="utf-8") as f:
            json.dump({"save_dir": new_dir}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def today():
    return datetime.now().date()


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


def item_rule_text(item):
    if item.get("mode") == "date":
        d = date.fromisoformat(item["date"])
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"
    return f"{int(item.get('days', 0))} 天后"


def range_key_for(r):
    if r <= 0:
        return "today"
    if r <= 3:
        return "3"
    if r <= 7:
        return "7"
    if r <= 30:
        return "30"
    if r <= 365:
        return "365"
    return "1000"


def default_color_for(r, overrides):
    if r < 0:
        return OVERDUE
    key = range_key_for(r)
    return overrides.get(key) or DEFAULT_COLORS.get(key) or FG_MAIN


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
                exe = sys.executable
                script = os.path.abspath(__file__)
                cmd = f'"{exe}" "{script}"'
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
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
        autostart = os.path.join(_home(), ".config", "autostart")
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
                        "Name=桌面倒计时\n"
                        f"Exec={sys.executable} {os.path.abspath(__file__)}\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            except OSError:
                pass
        else:
            try:
                os.remove(desktop)
            except OSError:
                pass


def make_button(parent, text, command, primary=False, **kw):
    bg = BTN_PRIMARY if primary else BTN_BG
    fg = "#ffffff" if primary else FG_MAIN
    abg = BTN_PRIMARY_HOVER if primary else BTN_HOVER
    opts = dict(bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
                relief="flat", bd=0, padx=12, pady=4,
                font=(UI_FONT, 10), cursor="hand2")
    opts.update(kw)
    return tk.Button(parent, text=text, command=command, **opts)


def center_window(win, parent=None):
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    if parent is not None:
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw = parent.winfo_width()
            x = px - w - 20
            if x < 10:
                x = px + pw + 20
            y = py
        except tk.TclError:
            x = (sw - w) // 2
            y = (sh - h) // 2
    else:
        x = (sw - w) // 2
        y = (sh - h) // 2
    x = max(10, min(x, sw - w - 10))
    y = max(10, min(y, sh - h - 10))
    win.geometry(f"+{x}+{y}")


# --------------------------------------------------------------------------- #
# 单实例锁（基于本机端口绑定，跨平台，无需额外依赖）
# --------------------------------------------------------------------------- #
_instance_lock_socket = None


def acquire_instance_lock():
    """尝试绑定本机端口以判断是否已有实例在运行。

    返回 True 表示当前是首个实例（已持有锁）；
    返回 False 表示端口已被占用，即已有实例在运行。
    若遇到端口占用以外的异常，为避免阻塞正常启动，仍返回 True。
    """
    global _instance_lock_socket
    if _instance_lock_socket is not None:
        return True
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
    except OSError as exc:
        s.close()
        if exc.errno == errno.EADDRINUSE:
            return False
        # 其他异常（极少见）不阻塞启动
        return True
    _instance_lock_socket = s
    return True


def release_instance_lock():
    """释放单实例锁（关闭占用端口的 socket）。"""
    global _instance_lock_socket
    if _instance_lock_socket is not None:
        try:
            _instance_lock_socket.close()
        except OSError:
            pass
        _instance_lock_socket = None


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def default_config():
    t = today().isoformat()
    return {
        "alpha": 0.90,
        "font_size": 25,
        "transparent_bg": True,
        "locked": False,
        "topmost": True,
        "auto_start": False,
        "hidden": False,
        "x": None,
        "y": None,
        "text_color": None,
        "time_color": None,
        "menu_text_color": None,
        "timer_colors": {},
        "items": [],
    }


def load_config():
    cfg = default_config()
    path = get_config_path()
    if not os.path.exists(path):
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    for k in ("alpha", "font_size", "transparent_bg", "locked", "topmost",
              "auto_start", "hidden", "x", "y", "text_color", "time_color",
              "menu_text_color", "timer_colors"):
        if k in data:
            cfg[k] = data[k]
    if isinstance(data.get("items"), list):
        cfg["items"] = [
            it for it in data["items"]
            if isinstance(it, dict) and it.get("name") and it.get("mode") in ("days", "date")
        ]
    return cfg


def save_config(cfg):
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print("保存配置失败:", exc, file=sys.stderr)


# --------------------------------------------------------------------------- #
# 主应用
# --------------------------------------------------------------------------- #
class CountdownApp:
    def __init__(self):
        # 存档文件不存在即视为第一次启动
        self._first_launch = not os.path.exists(get_config_path())
        self.cfg = load_config()
        self._hidden = bool(self.cfg.get("hidden", False))
        self._drag_anchor = None
        self.settings_win = None
        self.about_win = None
        self.text_settings_win = None
        self.guide_win = None
        self.tray_icon = None
        self._tray_queue = queue.Queue()
        self.row_name_labels = []
        self.row_days_labels = []
        self._purge_prompting = False
        self._purge_declined = set()

        self.root = tk.Tk()
        self.root.title("桌面倒计时")
        self.root.overrideredirect(True)
        try:
            self.root.attributes("-topmost", bool(self.cfg.get("topmost", True)))
        except tk.TclError:
            pass

        self.bg = BG_DARK
        if sys.platform.startswith("win") and self.cfg.get("transparent_bg", True):
            self.bg = TRANSPARENT_KEY
        self.root.configure(bg=self.bg)

        self._refresh_days_basis()
        self._build_ui()
        self._apply_bg_and_alpha()
        self.rebuild_rows()
        self._restore_position()
        self._tick()
        self._start_tray()
        self.root.after(80, self._poll_tray_queue)

        if not HAS_TRAY:
            self.root.bind("<Control-Shift-L>", lambda e: self._toggle_lock())

        if self._hidden:
            self.root.withdraw()
        elif self._first_launch:
            # 第一次启动：先落盘配置（下次启动便不再算首次），再弹出引导
            save_config(self.cfg)
            self.root.after(400, self.open_guide)

    # ---------------- 基础 ---------------- #
    def _refresh_days_basis(self):
        t = today().isoformat()
        changed = False
        for it in self.cfg.get("items", []):
            if it.get("mode") == "days" and it.get("base") != t:
                it["base"] = t
                changed = True
        if changed:
            save_config(self.cfg)

    def _is_locked(self):
        return bool(self.cfg.get("locked", False))

    def _poll_tray_queue(self):
        try:
            while True:
                fn = self._tray_queue.get_nowait()
                try:
                    fn()
                except Exception as exc:
                    print("托盘回调错误:", exc, file=sys.stderr)
        except queue.Empty:
            pass
        try:
            self.root.after(80, self._poll_tray_queue)
        except tk.TclError:
            pass

    # ---------------- 界面 ---------------- #
    def _build_ui(self):
        self.container = tk.Frame(self.root, bg=self.bg, bd=0, highlightthickness=0)
        self.container.pack(fill="both", expand=True, padx=16, pady=10)

        self.clock_label = tk.Label(
            self.container, text="", font=(UI_FONT, 9),
            fg=self.cfg.get("time_color") or FG_SUB, bg=self.bg, anchor="w",
        )
        self.clock_label.pack(fill="x")
        self.clock_label.bind("<Double-Button-1>", self._on_clock_double)
        self._bind_drag(self.clock_label)

        self.rows_frame = tk.Frame(self.container, bg=self.bg)
        self.rows_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.rows_frame.columnconfigure(0, weight=1)

    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._on_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_drag, add="+")
        for child in widget.winfo_children():
            self._bind_drag(child)

    # ---------------- 拖动 ---------------- #
    def _start_drag(self, event):
        if self._is_locked():
            self._drag_anchor = None
            return
        self._drag_anchor = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def _on_drag(self, event):
        if self._drag_anchor is None or self._is_locked():
            return
        dx, dy = self._drag_anchor
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _end_drag(self, event):
        if self._drag_anchor is None:
            return
        self._drag_anchor = None
        if self._is_locked():
            return
        try:
            self.cfg["x"] = self.root.winfo_x()
            self.cfg["y"] = self.root.winfo_y()
            save_config(self.cfg)
        except tk.TclError:
            pass

    # ---------------- 背景 & 透明度 ---------------- #
    def _apply_bg_and_alpha(self):
        use_key = bool(self.cfg.get("transparent_bg", True)) and sys.platform.startswith("win")
        self.bg = TRANSPARENT_KEY if use_key else BG_DARK
        self.root.configure(bg=self.bg)
        self._recolor(self.root)

        try:
            alpha = float(self.cfg.get("alpha", 0.9))
        except (TypeError, ValueError):
            alpha = 0.9
        alpha = min(1.0, max(0.15, alpha))
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            pass

        if sys.platform.startswith("win"):
            try:
                self.root.attributes("-transparentcolor", self.bg if use_key else "")
            except tk.TclError:
                self.bg = BG_DARK

        # 更新时钟颜色
        try:
            self.clock_label.configure(fg=self.cfg.get("time_color") or FG_SUB)
        except tk.TclError:
            pass

    def _recolor(self, widget):
        if isinstance(widget, tk.Toplevel):
            return
        try:
            widget.configure(bg=self.bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._recolor(child)

    # ---------------- 列表 ---------------- #
    def rebuild_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.row_name_labels.clear()
        self.row_days_labels.clear()

        fs = max(8, min(48, int(self.cfg.get("font_size", 25))))
        items = self.cfg.get("items", [])

        for i, item in enumerate(items):
            name_color = item.get("name_color") or self.cfg.get("text_color") or FG_MAIN
            name_lbl = tk.Label(
                self.rows_frame, text=str(item.get("name", "")),
                font=(UI_FONT, fs), fg=name_color, bg=self.bg, anchor="w",
                cursor="hand2",
            )
            name_lbl.grid(row=i, column=0, sticky="w", pady=1)

            days_lbl = tk.Label(
                self.rows_frame, text="",
                font=(UI_FONT, fs, "bold"), fg=ACCENT, bg=self.bg, anchor="e",
                cursor="hand2",
            )
            days_lbl.grid(row=i, column=1, sticky="e", padx=(24, 0), pady=1)

            self._bind_drag(name_lbl)
            self._bind_drag(days_lbl)

            name_lbl.bind("<Double-Button-1>",
                          lambda e, it=item: self._open_name_dialog(it))
            days_lbl.bind("<Double-Button-1>",
                          lambda e, it=item: self._open_time_dialog(it))

            self.row_name_labels.append((name_lbl, item))
            self.row_days_labels.append((days_lbl, item))

        if not items:
            hint = tk.Label(
                self.rows_frame, text="托盘菜单 → 新增倒计时",
                font=(UI_FONT, max(9, fs // 2)), fg=FG_SUB, bg=self.bg, anchor="w",
            )
            hint.grid(row=0, column=0, columnspan=2, sticky="w")
            self._bind_drag(hint)

    def refresh(self):
        if self._hidden:
            return
        t = today()

        # 指定日期已过期：确认后删除
        expired = []
        for it in self.cfg.get("items", []):
            if it.get("mode") != "date" or id(it) in self._purge_declined:
                continue
            try:
                if item_remaining(it, t) < 0:
                    expired.append(it)
            except Exception:
                pass
        if expired and not self._purge_prompting:
            self._purge_prompting = True
            try:
                names = "、".join(f"「{it.get('name', '')}」" for it in expired)
                ok = messagebox.askyesno(
                    "倒计时已过期",
                    f"{names} 的目标日期已过。\n是否删除？",
                    parent=self.root)
            finally:
                self._purge_prompting = False
            if ok:
                gone = {id(it) for it in expired}
                self.cfg["items"] = [it for it in self.cfg.get("items", [])
                                     if id(it) not in gone]
                save_config(self.cfg)
                self.rebuild_rows()
                self.refresh()
                return
            self._purge_declined.update(id(it) for it in expired)

        overrides = self.cfg.get("timer_colors", {}) or {}
        for label, item in self.row_days_labels:
            try:
                r = item_remaining(item, t)
            except Exception:
                try:
                    label.configure(text="数据错误", fg=OVERDUE)
                except tk.TclError:
                    pass
                continue
            if r > 0:
                text = f"{r}天"
            elif r == 0:
                text = "今天"
            else:
                text = "已过"
            color = item.get("timer_color") or default_color_for(r, overrides)
            try:
                label.configure(text=text, fg=color)
            except tk.TclError:
                pass
        for label, item in self.row_name_labels:
            c = item.get("name_color") or self.cfg.get("text_color") or FG_MAIN
            try:
                label.configure(fg=c)
            except tk.TclError:
                pass

    def _clock_text(self):
        now = datetime.now()
        wd = WEEKDAY_CN[now.weekday()]
        s = f"{now.strftime('%Y%m%d %H:%M:%S')} 周{wd}"
        if self._is_locked():
            s += "  🔒"
        return s

    def _tick(self):
        try:
            self.clock_label.configure(text=self._clock_text())
            if not self._hidden:
                self.refresh()
        except tk.TclError:
            return
        self.root.after(1000, self._tick)

    # ---------------- 双击入口 ---------------- #
    def _on_clock_double(self, event):
        if self._is_locked():
            return
        self.open_settings()

    def _open_name_dialog(self, item):
        if self._is_locked():
            return
        dlg = NameItemDialog(self.root, self, item)
        if dlg.result:
            item["name"] = dlg.result["name"]
            item["name_color"] = dlg.result["name_color"]
            save_config(self.cfg)
            self.rebuild_rows()
            self.refresh()

    def _open_time_dialog(self, item):
        if self._is_locked():
            return
        dlg = TimeItemDialog(self.root, self, item)
        if dlg.result:
            if dlg.result.get("delete"):
                self.delete_item(item)
                return
            if dlg.result["mode"] == "days":
                item["mode"] = "days"
                item["days"] = dlg.result["days"]
                item["base"] = today().isoformat()
                item.pop("date", None)
            else:
                item["mode"] = "date"
                item["date"] = dlg.result["date"]
                item.pop("days", None)
                item.pop("base", None)
            item["timer_color"] = dlg.result["timer_color"]
            save_config(self.cfg)
            self.rebuild_rows()
            self.refresh()

    def delete_item(self, item):
        items = self.cfg.get("items", [])
        if not any(it is item for it in items):
            return
        self.cfg["items"] = [it for it in items if it is not item]
        save_config(self.cfg)
        self.rebuild_rows()
        self.refresh()

    # ---------------- 位置 ---------------- #
    def _restore_position(self):
        try:
            self.root.update_idletasks()
            w = self.root.winfo_reqwidth()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
        except tk.TclError:
            return
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            x, y = sw - w - 40, 60
        x = max(0, min(int(x), max(0, sw - 60)))
        y = max(0, min(int(y), max(0, sh - 60)))
        self.root.geometry(f"+{x}+{y}")

    # ---------------- 托盘 ---------------- #
    def _start_tray(self):
        if not HAS_TRAY:
            print("未安装 pystray / Pillow，无法启用系统托盘", file=sys.stderr)
            return
        img = self._load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("显示/隐藏", self._tray_toggle_show, default=True),
            pystray.MenuItem("新增倒计时", self._tray_add),
            pystray.MenuItem("隐藏倒计时", self._tray_hide),
            pystray.MenuItem("显示倒计时", self._tray_show),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("锁定", self._tray_toggle_lock,
                             checked=lambda it: bool(self.cfg.get("locked", False))),
            pystray.MenuItem("最顶置", self._tray_toggle_topmost,
                             checked=lambda it: bool(self.cfg.get("topmost", True))),
            pystray.MenuItem("设置", self._tray_settings),
            pystray.MenuItem("使用引导", self._tray_guide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("关闭程序", self._tray_quit),
        )
        try:
            self.tray_icon = pystray.Icon("desktop_countdown", img, "桌面倒计时", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as exc:
            print("托盘启动失败:", exc, file=sys.stderr)

    def _load_tray_image(self, size=64):
        here = os.path.dirname(os.path.abspath(__file__))
        for name in ("image.png", "icon.png", "tray.png"):
            p = os.path.join(here, name)
            if os.path.exists(p):
                try:
                    img = Image.open(p).convert("RGBA")
                    return img.resize((size, size), Image.LANCZOS)
                except Exception:
                    pass
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, size - 4, size - 4), fill=(79, 195, 247, 255))
        d.ellipse((size // 2 - 6, size // 2 - 6, size // 2 + 6, size // 2 + 6),
                  fill=(255, 255, 255, 255))
        return img

    def _tray_toggle_show(self, icon=None, item=None):
        self._tray_queue.put(self._toggle_visibility)

    def _tray_add(self, icon=None, item=None):
        self._tray_queue.put(self._open_add_dialog)

    def _tray_hide(self, icon=None, item=None):
        self._tray_queue.put(self._hide_window)

    def _tray_show(self, icon=None, item=None):
        self._tray_queue.put(self._show_window)

    def _tray_toggle_lock(self, icon=None, item=None):
        self._tray_queue.put(self._toggle_lock)

    def _tray_toggle_topmost(self, icon=None, item=None):
        self._tray_queue.put(self._toggle_topmost)

    def _tray_settings(self, icon=None, item=None):
        self._tray_queue.put(self.open_settings)

    def _tray_guide(self, icon=None, item=None):
        self._tray_queue.put(self.open_guide)

    def _tray_quit(self, icon=None, item=None):
        self._tray_queue.put(self.quit_app)

    def _refresh_tray_menu(self):
        if self.tray_icon is not None:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    # ---------------- 状态动作 ---------------- #
    def _toggle_visibility(self):
        if self._hidden:
            self._show_window()
        else:
            self._hide_window()

    def _hide_window(self):
        self._hidden = True
        self.cfg["hidden"] = True
        save_config(self.cfg)
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _show_window(self):
        self._hidden = False
        self.cfg["hidden"] = False
        save_config(self.cfg)
        try:
            self.root.deiconify()
            self.root.lift()
        except tk.TclError:
            pass

    def _toggle_lock(self):
        self.cfg["locked"] = not bool(self.cfg.get("locked", False))
        save_config(self.cfg)
        self._apply_bg_and_alpha()
        self.rebuild_rows()
        self.refresh()
        self._refresh_tray_menu()

    def _toggle_topmost(self):
        self.cfg["topmost"] = not bool(self.cfg.get("topmost", True))
        try:
            self.root.attributes("-topmost", self.cfg["topmost"])
        except tk.TclError:
            pass
        save_config(self.cfg)
        self._refresh_tray_menu()

    # ---------------- 打开窗口 ---------------- #
    def open_settings(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.focus_force()
            return
        self.settings_win = SettingsWindow(self)

    def open_about(self):
        if self.about_win is not None and self.about_win.winfo_exists():
            self.about_win.lift()
            self.about_win.focus_force()
            return
        self.about_win = AboutWindow(self.root, self)

    def open_text_settings(self):
        if self.text_settings_win is not None and self.text_settings_win.winfo_exists():
            self.text_settings_win.lift()
            self.text_settings_win.focus_force()
            return
        self.text_settings_win = TextSettingsWindow(self.root, self)

    def open_guide(self):
        if self.guide_win is not None and self.guide_win.winfo_exists():
            self.guide_win.lift()
            self.guide_win.focus_force()
            return
        self.guide_win = GuideWindow(self.root)

    def _open_add_dialog(self):
        if self._is_locked():
            return
        dlg = AddItemDialog(self.root, self)
        if dlg.result:
            self.cfg["items"].append(dlg.result)
            save_config(self.cfg)
            self.rebuild_rows()
            self.refresh()

    def apply_all(self):
        self._apply_bg_and_alpha()
        self.rebuild_rows()
        self.refresh()

    # ---------------- 退出 ---------------- #
    def quit_app(self):
        try:
            self.cfg["x"] = self.root.winfo_x()
            self.cfg["y"] = self.root.winfo_y()
            save_config(self.cfg)
        except tk.TclError:
            pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self):
        self.root.mainloop()


# --------------------------------------------------------------------------- #
# 文字单设置（双击名称）
# --------------------------------------------------------------------------- #
class NameItemDialog(tk.Toplevel):
    def __init__(self, parent, app, item):
        super().__init__(parent)
        self.app = app
        self.item = item
        self.result = None
        self.custom_color = item.get("name_color")

        self.title("文字单设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(body, text="名称", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        self.name_var = tk.StringVar(value=item.get("name", ""))
        tk.Entry(body, textvariable=self.name_var, bg=ENTRY_BG, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat",
                 font=(UI_FONT, 11)).pack(fill="x", pady=(4, 10))

        tk.Label(body, text="颜色", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")

        self.color_choice = tk.StringVar(
            value="custom" if item.get("name_color") else "default")
        cf = tk.Frame(body, bg=BG_PANEL)
        cf.pack(fill="x", pady=(4, 6))
        for text, val in (("默认", "default"), ("自定义", "custom")):
            tk.Radiobutton(
                cf, text=text, value=val, variable=self.color_choice,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        make_button(body, "选色", self._pick_color).pack(anchor="w", pady=(2, 12))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(4, 0))
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _pick_color(self):
        dlg = PickColorDialog(
            self, self.app,
            initial_color=self.custom_color or FG_MAIN,
            with_alpha=False,
        )
        if dlg.result:
            self.custom_color = dlg.result[0]
            self.color_choice.set("custom")

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "名称不能为空", parent=self)
            return
        color = self.custom_color if self.color_choice.get() == "custom" else None
        self.result = {"name": name, "name_color": color}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 时间单设置（双击天数 / 时间）
# --------------------------------------------------------------------------- #
class TimeItemDialog(tk.Toplevel):
    def __init__(self, parent, app, item):
        super().__init__(parent)
        self.app = app
        self.item = item
        self.result = None
        self.custom_color = item.get("timer_color")

        self.title("时间单设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text=f"条目：{item.get('name', '')}",
                 bg=BG_PANEL, fg=FG_SUB, font=(UI_FONT, 9),
                 anchor="w").grid(row=0, column=0, columnspan=3,
                                  sticky="w", pady=(0, 8))

        tk.Label(body, text="模式", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value=item.get("mode", "days"))
        mf = tk.Frame(body, bg=BG_PANEL)
        mf.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0))
        for text, val in (("天数倒计", "days"), ("日期倒计", "date")):
            tk.Radiobutton(
                mf, text=text, value=val, variable=self.mode_var,
                command=self._update_state,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        tk.Label(body, text="天数", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        self.days_var = tk.StringVar(
            value=str(item.get("days", 30)) if item.get("mode") != "date" else "30")
        self.days_entry = tk.Entry(body, textvariable=self.days_var,
                                   bg=ENTRY_BG, fg=FG_MAIN,
                                   disabledbackground="#171c22",
                                   disabledforeground="#5a6773",
                                   insertbackground=FG_MAIN,
                                   relief="flat", font=(UI_FONT, 10), width=8)
        self.days_entry.grid(row=2, column=1, sticky="w", padx=(8, 0))
        tk.Label(body, text=f"（0 ~ {MAX_DAYS}）", bg=BG_PANEL, fg=FG_SUB,
                 font=(UI_FONT, 9)).grid(row=2, column=2, sticky="w")

        tk.Label(body, text="日期", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=3, column=0, sticky="w", pady=4)
        init_date_text = ""
        if item.get("mode") == "date":
            try:
                d = date.fromisoformat(item["date"])
                init_date_text = f"{d.year}年{d.month:02d}月{d.day:02d}日"
            except Exception:
                init_date_text = ""
        self.date_var = tk.StringVar(value=init_date_text)
        self.date_entry = tk.Entry(body, textvariable=self.date_var,
                                   bg=ENTRY_BG, fg=FG_MAIN,
                                   disabledbackground="#171c22",
                                   disabledforeground="#5a6773",
                                   insertbackground=FG_MAIN,
                                   relief="flat", font=(UI_FONT, 10))
        self.date_entry.grid(row=3, column=1, columnspan=2, sticky="ew",
                             padx=(8, 0), pady=4)

        tk.Label(body, text="颜色", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=4, column=0, sticky="w", pady=(10, 4))
        self.color_choice = tk.StringVar(
            value="custom" if item.get("timer_color") else "default")
        cf = tk.Frame(body, bg=BG_PANEL)
        cf.grid(row=4, column=1, columnspan=2, sticky="w",
                padx=(8, 0), pady=(10, 4))
        for text, val in (("默认", "default"), ("自定义", "custom")):
            tk.Radiobutton(
                cf, text=text, value=val, variable=self.color_choice,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))
        make_button(body, "选色", self._pick_color).grid(
            row=5, column=1, sticky="w", padx=(8, 0), pady=(0, 10))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        make_button(btns, "删除", self._delete).pack(side="left")
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_state()
        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _update_state(self):
        if self.mode_var.get() == "days":
            self.days_entry.configure(state="normal")
            self.date_entry.configure(state="disabled")
        else:
            self.days_entry.configure(state="disabled")
            self.date_entry.configure(state="normal")

    def _pick_color(self):
        dlg = PickColorDialog(
            self, self.app,
            initial_color=self.custom_color or ACCENT,
            with_alpha=False,
        )
        if dlg.result:
            self.custom_color = dlg.result[0]
            self.color_choice.set("custom")

    def _ok(self):
        mode = self.mode_var.get()
        if mode == "days":
            try:
                n = int(self.days_var.get().strip())
            except ValueError:
                messagebox.showwarning("提示", "天数必须为整数", parent=self)
                return
            if not (0 <= n <= MAX_DAYS):
                messagebox.showwarning("提示", f"天数必须在 0 ~ {MAX_DAYS}", parent=self)
                return
            data = {"mode": "days", "days": n}
        else:
            try:
                d = parse_date_str(self.date_var.get())
            except ValueError as exc:
                messagebox.showwarning("提示", str(exc), parent=self)
                return
            if (d - today()).days < 0:
                messagebox.showwarning("提示", "目标日期不能早于今天", parent=self)
                return
            data = {"mode": "date", "date": d.isoformat()}
        data["timer_color"] = (self.custom_color
                               if self.color_choice.get() == "custom" else None)
        self.result = data
        self.destroy()

    def _delete(self):
        name = self.item.get("name", "")
        if not messagebox.askyesno("删除倒计时", f"确定删除「{name}」？",
                                   parent=self):
            return
        self.result = {"delete": True}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 新增倒计时
# --------------------------------------------------------------------------- #
class AddItemDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.result = None

        self.title("新增倒计时")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="名称", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar(value="")
        tk.Entry(body, textvariable=self.name_var, bg=ENTRY_BG, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat",
                 font=(UI_FONT, 10)).grid(row=0, column=1, columnspan=2,
                                          sticky="ew", pady=4, padx=(8, 0))

        tk.Label(body, text="方式", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="days")
        mf = tk.Frame(body, bg=BG_PANEL)
        mf.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0))
        for text, val in (("n 天后", "days"), ("指定日期", "date")):
            tk.Radiobutton(
                mf, text=text, value=val, variable=self.mode_var,
                command=self._update_state,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        tk.Label(body, text="天数", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        self.days_var = tk.StringVar(value="30")
        self.days_entry = tk.Entry(body, textvariable=self.days_var,
                                   bg=ENTRY_BG, fg=FG_MAIN,
                                   disabledbackground="#171c22",
                                   disabledforeground="#5a6773",
                                   insertbackground=FG_MAIN,
                                   relief="flat", font=(UI_FONT, 10), width=8)
        self.days_entry.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        tk.Label(body, text="日期", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=3, column=0, sticky="w", pady=4)
        self.date_var = tk.StringVar(value=(today() + timedelta(days=30)).strftime("%Y年%m月%d日"))
        self.date_entry = tk.Entry(body, textvariable=self.date_var,
                                   bg=ENTRY_BG, fg=FG_MAIN,
                                   disabledbackground="#171c22",
                                   disabledforeground="#5a6773",
                                   insertbackground=FG_MAIN,
                                   relief="flat", font=(UI_FONT, 10))
        self.date_entry.grid(row=3, column=1, columnspan=2, sticky="ew",
                             padx=(8, 0), pady=4)

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_state()
        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _update_state(self):
        if self.mode_var.get() == "days":
            self.days_entry.configure(state="normal")
            self.date_entry.configure(state="disabled")
        else:
            self.days_entry.configure(state="disabled")
            self.date_entry.configure(state="normal")

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请填写名称", parent=self)
            return
        t = today()
        if self.mode_var.get() == "days":
            try:
                n = int(self.days_var.get().strip())
            except ValueError:
                messagebox.showwarning("提示", "天数必须为整数", parent=self)
                return
            if not (0 <= n <= MAX_DAYS):
                messagebox.showwarning("提示", f"天数必须在 0 ~ {MAX_DAYS}", parent=self)
                return
            self.result = {
                "name": name, "mode": "days", "days": n,
                "base": t.isoformat(),
                "name_color": None, "timer_color": None,
            }
        else:
            try:
                d = parse_date_str(self.date_var.get())
            except ValueError as exc:
                messagebox.showwarning("提示", str(exc), parent=self)
                return
            delta = (d - t).days
            if delta < 0:
                messagebox.showwarning("提示", "目标日期不能早于今天", parent=self)
                return
            if delta > MAX_DAYS:
                messagebox.showwarning("提示", f"距离今天不能超过 {MAX_DAYS} 天", parent=self)
                return
            self.result = {
                "name": name, "mode": "date", "date": d.isoformat(),
                "name_color": None, "timer_color": None,
            }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 选色器
# --------------------------------------------------------------------------- #
class PickColorDialog(tk.Toplevel):
    PRESETS = [
        ("黑", "#000000"), ("白", "#FFFFFF"), ("红", "#EF5350"),
        ("橙", "#FF9800"), ("黄", "#FFCA28"), ("绿", "#66BB6A"),
        ("青", "#26C6DA"), ("蓝", "#42A5F5"), ("紫", "#AB47BC"),
        ("粉", "#F06292"), ("灰", "#90A4AE"),
    ]

    def __init__(self, parent, app, initial_color="#ffffff", initial_alpha=0.9,
                 with_alpha=True):
        super().__init__(parent)
        self.app = app
        self.result = None
        self.current_color = self._norm(initial_color)

        self.title("选色器")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # 预设颜色
        tk.Label(body, text="预设颜色", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        pg = tk.Frame(body, bg=BG_PANEL)
        pg.pack(fill="x", pady=(4, 8))
        for i, (label, hexv) in enumerate(self.PRESETS):
            b = tk.Button(pg, text=label, bg=hexv,
                          fg="#000000" if label in ("白", "黄") else "#ffffff",
                          activebackground=hexv, relief="flat", bd=0,
                          font=(UI_FONT, 9), width=4, cursor="hand2")
            b.configure(command=lambda c=hexv: self._set_color(c))
            b.grid(row=i // 6, column=i % 6, padx=2, pady=2, sticky="ew")
        for c in range(6):
            pg.columnconfigure(c, weight=1)

        # RGB
        tk.Label(body, text="RGB 颜色", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        rgb_row = tk.Frame(body, bg=BG_PANEL)
        rgb_row.pack(fill="x", pady=(4, 4))
        self.r_var, self.g_var, self.b_var = (tk.StringVar(), tk.StringVar(),
                                               tk.StringVar())
        r, g, b = self._to_rgb(self.current_color)
        self.r_var.set(str(r))
        self.g_var.set(str(g))
        self.b_var.set(str(b))
        for tag, var in (("R", self.r_var), ("G", self.g_var), ("B", self.b_var)):
            tk.Label(rgb_row, text=tag, bg=BG_PANEL, fg=FG_MAIN,
                     font=(UI_FONT, 10)).pack(side="left")
            tk.Entry(rgb_row, textvariable=var, bg=ENTRY_BG, fg=FG_MAIN,
                     insertbackground=FG_MAIN, relief="flat",
                     width=5, font=(UI_FONT, 10)).pack(side="left",
                                                       padx=(2, 8))
        make_button(rgb_row, "改变", self._apply_rgb).pack(side="left")

        # 透明度（仅全局设置时显示）
        self.alpha_var = tk.DoubleVar(
            value=max(0.15, min(1.0, float(initial_alpha))))
        if with_alpha:
            tk.Label(body, text="透明度 (ALPHA)", bg=BG_PANEL, fg=FG_MAIN,
                     font=(UI_FONT, 10), anchor="w").pack(fill="x", pady=(8, 0))
            tk.Scale(
                body, from_=0.15, to=1.0, resolution=0.05, orient="horizontal",
                variable=self.alpha_var, bg=BG_PANEL, fg=FG_MAIN,
                troughcolor=ENTRY_BG, highlightthickness=0, bd=0,
                length=260, font=(UI_FONT, 9),
            ).pack(fill="x", pady=(2, 8))

        # 预览
        tk.Label(body, text="颜色预览", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        self.preview = tk.Label(body, text="", bg=self.current_color,
                                height=2, relief="solid", bd=1)
        self.preview.pack(fill="x", pady=(4, 10))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x")
        make_button(btns, "确定", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    @staticmethod
    def _norm(color):
        c = str(color).strip()
        if not c.startswith("#"):
            c = "#" + c
        if len(c) == 4:
            c = "#" + "".join(ch * 2 for ch in c[1:])
        if len(c) != 7:
            return "#ffffff"
        try:
            int(c[1:], 16)
        except ValueError:
            return "#ffffff"
        return c.lower()

    @staticmethod
    def _to_rgb(color):
        c = color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    def _set_color(self, color):
        self.current_color = self._norm(color)
        r, g, b = self._to_rgb(self.current_color)
        self.r_var.set(str(r))
        self.g_var.set(str(g))
        self.b_var.set(str(b))
        self.preview.configure(bg=self.current_color)

    def _apply_rgb(self):
        try:
            r = int(self.r_var.get())
            g = int(self.g_var.get())
            b = int(self.b_var.get())
        except ValueError:
            return
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        self.r_var.set(str(r))
        self.g_var.set(str(g))
        self.b_var.set(str(b))
        self.current_color = f"#{r:02x}{g:02x}{b:02x}"
        self.preview.configure(bg=self.current_color)

    def _ok(self):
        self.result = (self.current_color, float(self.alpha_var.get()))
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 计时颜色更改
# --------------------------------------------------------------------------- #
class TimerColorsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.result = None
        overrides = dict(app.cfg.get("timer_colors") or {})
        self.overrides = overrides
        self.custom_map = {k: overrides.get(k) for k in RANGE_KEYS}
        self.choice_vars = {}

        self.title("计时颜色更改")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(2, weight=1)

        for i, key in enumerate(RANGE_KEYS):
            label = RANGE_LABELS[key]
            default_color = DEFAULT_COLORS[key]

            tk.Label(body, text=label, bg=BG_PANEL, fg=FG_MAIN,
                     font=(UI_FONT, 10)).grid(row=i, column=0, sticky="w",
                                              pady=4)
            var = tk.StringVar(
                value="custom" if self.custom_map.get(key) else "default")
            self.choice_vars[key] = var

            rf = tk.Frame(body, bg=BG_PANEL)
            rf.grid(row=i, column=1, columnspan=2, sticky="w",
                    padx=(12, 0), pady=4)
            tk.Radiobutton(
                rf, text=f"默认：{label == '今天' and '白' or ''}",
                value="default", variable=var,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 8))
            swatch = tk.Label(rf, text="   ", bg=default_color, width=3,
                              relief="solid", bd=1)
            swatch.pack(side="left", padx=(0, 12))

            tk.Radiobutton(
                rf, text="自定义", value="custom", variable=var,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 8))
            make_button(rf, "选色",
                        lambda k=key: self._pick(k)).pack(side="left")

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=len(RANGE_KEYS), column=0, columnspan=3,
                  sticky="ew", pady=(10, 0))
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _pick(self, key):
        dlg = PickColorDialog(
            self, self.app,
            initial_color=self.custom_map.get(key) or DEFAULT_COLORS[key],
            initial_alpha=float(self.app.cfg.get("alpha", 0.9)),
        )
        if dlg.result:
            color, alpha = dlg.result
            self.custom_map[key] = color
            self.choice_vars[key].set("custom")
            self.app.cfg["alpha"] = round(alpha, 2)
            self.app._apply_bg_and_alpha()

    def _ok(self):
        result = {}
        for key in RANGE_KEYS:
            if self.choice_vars[key].get() == "custom" and self.custom_map.get(key):
                result[key] = self.custom_map[key]
        self.result = result
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 默认设置
# --------------------------------------------------------------------------- #
class DefaultSettingsWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.title("默认设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        # 文字大小
        tk.Label(body, text="文字大小", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.font_var = tk.IntVar(
            value=max(8, min(48, int(app.cfg.get("font_size", 25)))))
        tk.Spinbox(
            body, from_=8, to=48, textvariable=self.font_var, width=5,
            bg=ENTRY_BG, fg=FG_MAIN, buttonbackground=BTN_BG,
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        # 文字颜色
        self.text_choice = tk.StringVar(
            value="custom" if app.cfg.get("text_color") else "default")
        self.text_color = app.cfg.get("text_color")
        self._color_row(body, 1, "文字颜色", self.text_choice,
                        lambda: self.text_color,
                        lambda c: setattr(self, "text_color", c))

        # 计时器颜色
        tk.Label(body, text="计时器颜色", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        make_button(body, "更改", self._open_timer_colors).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # 时间颜色
        self.time_choice = tk.StringVar(
            value="custom" if app.cfg.get("time_color") else "default")
        self.time_color = app.cfg.get("time_color")
        self._color_row(body, 3, "时间颜色", self.time_choice,
                        lambda: self.time_color,
                        lambda c: setattr(self, "time_color", c))

        # 菜单文字颜色
        self.menu_choice = tk.StringVar(
            value="custom" if app.cfg.get("menu_text_color") else "default")
        self.menu_color = app.cfg.get("menu_text_color")
        self._color_row(body, 4, "菜单文字颜色", self.menu_choice,
                        lambda: self.menu_color,
                        lambda c: setattr(self, "menu_color", c))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _color_row(self, body, row, label, choice_var, getter, setter):
        tk.Label(body, text=label, bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=row, column=0, sticky="w", pady=4)
        rf = tk.Frame(body, bg=BG_PANEL)
        rf.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        tk.Radiobutton(
            rf, text="默认", value="default", variable=choice_var,
            bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
            activebackground=BG_PANEL, activeforeground=FG_MAIN,
            font=(UI_FONT, 10), bd=0, highlightthickness=0,
        ).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            rf, text="自定义", value="custom", variable=choice_var,
            bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
            activebackground=BG_PANEL, activeforeground=FG_MAIN,
            font=(UI_FONT, 10), bd=0, highlightthickness=0,
        ).pack(side="left", padx=(0, 8))

        def pick():
            dlg = PickColorDialog(
                self, self.app,
                initial_color=getter() or FG_MAIN,
                initial_alpha=float(self.app.cfg.get("alpha", 0.9)),
            )
            if dlg.result:
                color, alpha = dlg.result
                setter(color)
                choice_var.set("custom")
                self.app.cfg["alpha"] = round(alpha, 2)
                self.app._apply_bg_and_alpha()

        make_button(rf, "选色", pick).pack(side="left")

    def _open_timer_colors(self):
        dlg = TimerColorsDialog(self, self.app)
        if dlg.result is not None:
            self.app.cfg["timer_colors"] = dlg.result
            save_config(self.app.cfg)
            self.app.refresh()

    def _ok(self):
        try:
            fs = int(self.font_var.get())
        except (tk.TclError, ValueError):
            fs = 25
        self.app.cfg["font_size"] = max(8, min(48, fs))
        self.app.cfg["text_color"] = (self.text_color
                                      if self.text_choice.get() == "custom" else None)
        self.app.cfg["time_color"] = (self.time_color
                                      if self.time_choice.get() == "custom" else None)
        self.app.cfg["menu_text_color"] = (self.menu_color
                                           if self.menu_choice.get() == "custom" else None)
        save_config(self.app.cfg)
        self.app.apply_all()
        self.destroy()

    def _cancel(self):
        self.destroy()


# --------------------------------------------------------------------------- #
# 文字设置
# --------------------------------------------------------------------------- #
class TextSettingsWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.title("文字设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="文字大小", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.font_var = tk.IntVar(
            value=max(8, min(48, int(app.cfg.get("font_size", 25)))))
        tk.Spinbox(
            body, from_=8, to=48, textvariable=self.font_var, width=5,
            bg=ENTRY_BG, fg=FG_MAIN, buttonbackground=BTN_BG,
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        make_button(body, "默认设置", self._open_default).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        make_button(btns, "完成", self._ok, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.grab_set()
        self.wait_window(self)

    def _open_default(self):
        DefaultSettingsWindow(self, self.app)
        try:
            self.font_var.set(max(8, min(48,
                                         int(self.app.cfg.get("font_size", 25)))))
        except Exception:
            pass

    def _ok(self):
        try:
            fs = int(self.font_var.get())
        except (tk.TclError, ValueError):
            fs = 25
        self.app.cfg["font_size"] = max(8, min(48, fs))
        save_config(self.app.cfg)
        self.app.apply_all()
        self.destroy()

    def _cancel(self):
        self.destroy()


# --------------------------------------------------------------------------- #
# 使用引导
# --------------------------------------------------------------------------- #
GUIDE_STEPS = [
    (
        "欢迎使用「桌面倒计时」",
        [
            "这是一个常驻桌面的倒计时清单，一个窗口同时看住多个「还有多少天」。",
            "两种计时方式：n 天后（每天自动顺延）、指定日期（固定倒数）。",
            "第一次启动会自动弹出本引导，之后可在托盘菜单 → 使用引导 再次打开。",
        ],
    ),
    (
        "一切从托盘开始",
        [
            "程序启动后会在系统托盘（右下角 / 菜单栏）显示图标。",
            "左键单击图标：显示 / 隐藏主界面。",
            "右键单击图标：打开完整菜单（新增倒计时、锁定、最顶置、设置、使用引导、关闭程序）。",
            "如果托盘里看不到图标，请点开折叠区（^）找一找。",
        ],
    ),
    (
        "新增与编辑条目",
        [
            "托盘菜单 → 新增倒计时，填写名称并选择「n 天后」或「指定日期」。",
            "双击条目的名称：修改文字内容与名称颜色。",
            "双击条目的天数：修改时间规则与计时颜色。",
            "时间单设置 → 删除：删除该条目；指定日期已过的条目会自动移除。",
        ],
    ),
    (
        "摆放与锁定",
        [
            "按住主界面任意文字即可拖动窗口，位置会自动记住。",
            "托盘菜单 → 锁定：界面变淡且不可拖动、不可编辑，防止误触。",
            "再次点击「锁定」即可解除。",
        ],
    ),
    (
        "外观与设置",
        [
            "双击左上角的时间行，或托盘菜单 → 设置，打开设置窗口。",
            "可调整文字大小、文字 / 时间颜色、分档计时颜色、透明度、存档位置、开机自启动。",
            "设置 → 文字设置 → 默认设置，可统一修改颜色与计时档位。",
        ],
    ),
]


class GuideWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.index = 0

        self.title("使用引导")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        self.step_label = tk.Label(
            body, text="", bg=BG_PANEL, fg=FG_SUB,
            font=(UI_FONT, 9), anchor="w")
        self.step_label.pack(fill="x")

        self.text = tk.Text(
            body, width=64, height=9, wrap="word",
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            highlightthickness=0, cursor="arrow", insertwidth=0,
            font=(UI_FONT, 10), spacing1=1, spacing2=2, spacing3=4,
        )
        self.text.pack(fill="both", expand=True, pady=(6, 10))
        self.text.tag_configure("h", font=(UI_FONT, 13, "bold"),
                                foreground=ACCENT, spacing3=8)
        self.text.tag_configure("b", font=(UI_FONT, 10), foreground=FG_MAIN,
                                lmargin1=12, lmargin2=12)
        self.text.bind("<Key>", lambda e: "break")

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x")
        self.next_btn = make_button(btns, "下一步", self._next, primary=True)
        self.next_btn.pack(side="right")
        self.prev_btn = make_button(btns, "上一步", self._prev)
        self.prev_btn.pack(side="right", padx=(0, 8))
        make_button(btns, "跳过", self._close).pack(side="left")

        self._render()
        center_window(self, parent)
        self.grab_set()

    def _render(self):
        title, lines = GUIDE_STEPS[self.index]
        self.step_label.configure(
            text=f"第 {self.index + 1} / {len(GUIDE_STEPS)} 步")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", title + "\n", "h")
        for line in lines:
            self.text.insert("end", line + "\n", "b")
        self.text.configure(state="disabled")

        self.prev_btn.configure(state="normal" if self.index > 0 else "disabled")
        self.next_btn.configure(
            text="开始使用" if self.index == len(GUIDE_STEPS) - 1 else "下一步")

    def _next(self):
        if self.index >= len(GUIDE_STEPS) - 1:
            self._close()
            return
        self.index += 1
        self._render()

    def _prev(self):
        if self.index <= 0:
            return
        self.index -= 1
        self._render()

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# --------------------------------------------------------------------------- #
# 关于
# --------------------------------------------------------------------------- #
class AboutWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._seq = 0

        self.title("关于")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(parent)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=(14, 6))

        self.text = tk.Text(
            body, width=72, height=20, wrap="word",
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            highlightthickness=0, cursor="arrow", insertwidth=0,
            font=(UI_FONT, 10), spacing1=1, spacing3=1,
        )
        self.text.pack(fill="both", expand=True)

        self._configure_tags()
        self._fill_content()
        self.text.configure(state="disabled")
        self.text.bind("<Key>", lambda e: "break")

        self.status = tk.Label(self, text="", bg=BG_PANEL, fg=ACCENT,
                               anchor="w", font=(UI_FONT, 9))
        self.status.pack(fill="x", padx=16)

        bottom = tk.Frame(self, bg=BG_PANEL)
        bottom.pack(fill="x", padx=16, pady=(6, 14))
        make_button(bottom, "关闭", self.destroy, primary=True).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        center_window(self, parent)
        self.grab_set()

    def _configure_tags(self):
        t = self.text
        t.tag_configure("title", font=(UI_FONT, 16, "bold"),
                        foreground=ACCENT, spacing3=2)
        t.tag_configure("ver", font=(UI_FONT, 10),
                        foreground=FG_SUB, spacing3=6)
        t.tag_configure("h", font=(UI_FONT, 10, "bold"),
                        foreground=ACCENT, spacing1=9, spacing3=3)
        t.tag_configure("b", font=(UI_FONT, 10), foreground=FG_MAIN,
                        lmargin1=14, lmargin2=14)
        t.tag_configure("s", font=(UI_FONT, 9), foreground=FG_SUB,
                        lmargin1=14, lmargin2=14)

    def _insert_link(self, text, mode, payload):
        self._seq += 1
        tag = f"lnk{self._seq}"
        self.text.tag_configure(tag, foreground=LINK_COLOR, underline=True)
        self.text.tag_bind(tag, "<Button-1>",
                           lambda e, m=mode, p=payload: self._on_link(m, p))
        self.text.tag_bind(tag, "<Enter>",
                           lambda e: self.text.configure(cursor="hand2"))
        self.text.tag_bind(tag, "<Leave>",
                           lambda e: self.text.configure(cursor="arrow"))
        self.text.insert("end", text, tag)
        self.text.tag_raise(tag)

    def _fill_content(self):
        add = self.text.insert

        add("end", "无名小工具\n", "title")
        add("end", f"{APP_VERSION}\n", "ver")

        add("end", "更新日志\n", "h")
        add("end", f"{APP_VERSION}\n", "h")
        for line in (
            "· 新增系统托盘图标：左键显示/隐藏，右键完整菜单",
            "· 主界面改为双击编辑：名称、时间各自独立设置",
            "· 移除主窗口右键菜单，所有操作统一走托盘",
            "· 新增锁定虚化：锁定时主界面变淡，须从托盘解锁",
            "· 新增文字单设置 / 时间单设置（含颜色自定义）",
            "· 新增默认计时颜色（今天 / 3天 / 7天 / 30天 / 365天 / 1000天）",
            "· 新增透明度与 RGB 选色器",
            "· 新增开机自启动（Windows）",
            "· 新增存档位置自定义",
            "· 版本号更新为 Beta 0.2",
        ):
            add("end", line + "\n", "b")

        add("end", "作者：", "h")
        self._insert_link("四天不晚", "open", BILI_URL)
        add("end", "\n", "b")
        add("end", "只是一个学牲罢了。\n", "s")
        add("end", "注：本程序部分为 AI 辅助编写。\n", "s")

        add("end", "反馈 / 交流\n", "h")
        for label, (number, url, name) in (
            ("反馈群：", QQ_FEEDBACK),
            ("交流群：", QQ_CHAT),
        ):
            add("end", label, "b")
            self._insert_link(number, "copy", number)
            add("end", "　", "b")
            self._insert_link(f"点击加入群聊【{name}】", "open", url)
            add("end", "\n", "b")

        add("end", "征集\n", "h")
        add("end", "请加群：", "b")
        number, url, name = QQ_COLLECT
        self._insert_link(number, "copy", number)
        add("end", "　", "b")
        self._insert_link(f"点击加入群聊【{name}】", "open", url)
        add("end", "\n", "b")
        add("end", "或发送至邮箱：", "b")
        self._insert_link(EMAIL, "copy", EMAIL)
        add("end", "\n", "b")

    def _on_link(self, mode, payload):
        if mode == "copy":
            try:
                self.clipboard_clear()
                self.clipboard_append(payload)
                self.update_idletasks()
                self.status.configure(text=f"已复制：{payload}")
            except tk.TclError:
                self.status.configure(text="复制失败，请手动选择文本复制")
        else:
            try:
                webbrowser.open(payload)
                self.status.configure(text="已在浏览器中打开")
            except Exception:
                self.status.configure(text="无法打开浏览器，请手动访问：" + payload)
        try:
            self.after(2500, lambda: self.status.configure(text=""))
        except tk.TclError:
            pass


# --------------------------------------------------------------------------- #
# 主设置窗口
# --------------------------------------------------------------------------- #
class SettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app

        self.title("设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.transient(app.root)
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build()
        center_window(self, app.root)
        self.grab_set()

    def _build(self):
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        make_button(body, "新增倒计时", self._add_item).pack(fill="x", pady=3)

        # 最顶置
        row1 = tk.Frame(body, bg=BG_PANEL)
        row1.pack(fill="x", pady=3)
        tk.Label(row1, text="最顶置", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=10, anchor="w").pack(side="left")
        self.topmost_var = tk.StringVar(
            value="on" if self.app.cfg.get("topmost", True) else "off")
        for t, v in (("关", "off"), ("开", "on")):
            tk.Radiobutton(
                row1, text=t, value=v, variable=self.topmost_var,
                command=self._apply_topmost,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        # 开机自启动
        row2 = tk.Frame(body, bg=BG_PANEL)
        row2.pack(fill="x", pady=3)
        tk.Label(row2, text="开机自启动", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=10, anchor="w").pack(side="left")
        self.autostart_var = tk.StringVar(
            value="on" if self.app.cfg.get("auto_start", False) else "off")
        for t, v in (("关", "off"), ("开", "on")):
            tk.Radiobutton(
                row2, text=t, value=v, variable=self.autostart_var,
                command=self._apply_autostart,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        make_button(body, "文字设置", self._open_text_settings).pack(
            fill="x", pady=3)

        # 存档位置
        row3 = tk.Frame(body, bg=BG_PANEL)
        row3.pack(fill="x", pady=3)
        tk.Label(row3, text="存档位置", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=10, anchor="w").pack(side="left")
        self.save_dir_label = tk.Label(
            row3, text=get_save_dir(), bg=BG_PANEL, fg=FG_SUB,
            font=(UI_FONT, 9), anchor="w")
        self.save_dir_label.pack(side="left", fill="x", expand=True, padx=(6, 6))
        make_button(row3, "选择文件夹", self._choose_save_dir).pack(side="right")

        make_button(body, "关于", self._open_about).pack(fill="x", pady=3)
        make_button(body, "清除所有设置", self._clear_all).pack(fill="x", pady=3)
        make_button(body, "关闭程序", self._close_app).pack(fill="x", pady=3)

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(12, 0))
        make_button(btns, "完成", self._done, primary=True).pack(side="right")
        make_button(btns, "取消", self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())

    def _apply_topmost(self):
        self.app.cfg["topmost"] = (self.topmost_var.get() == "on")
        try:
            self.app.root.attributes("-topmost", self.app.cfg["topmost"])
        except tk.TclError:
            pass
        save_config(self.app.cfg)
        self.app._refresh_tray_menu()

    def _apply_autostart(self):
        on = self.autostart_var.get() == "on"
        self.app.cfg["auto_start"] = on
        save_config(self.app.cfg)
        set_auto_start(on)

    def _open_text_settings(self):
        self.app.open_text_settings()
        try:
            self.lift()
        except tk.TclError:
            pass

    def _choose_save_dir(self):
        d = filedialog.askdirectory(parent=self, initialdir=get_save_dir())
        if not d:
            return
        save_config(self.app.cfg)
        set_save_dir(d)
        save_config(self.app.cfg)
        try:
            self.save_dir_label.configure(text=d)
        except tk.TclError:
            pass
        messagebox.showinfo("提示", f"存档位置已更改为：\n{d}", parent=self)

    def _add_item(self):
        dlg = AddItemDialog(self, self.app)
        if dlg.result:
            self.app.cfg["items"].append(dlg.result)
            save_config(self.app.cfg)
            self.app.rebuild_rows()
            self.app.refresh()

    def _open_about(self):
        self.app.open_about()

    def _clear_all(self):
        if not messagebox.askyesno(
            "清除", "是否确认清除？是将会程序初始化", parent=self
        ):
            return
        self.app.cfg = default_config()
        save_config(self.app.cfg)
        self.app._apply_bg_and_alpha()
        self.app.rebuild_rows()
        self.app.refresh()
        self.app._refresh_tray_menu()
        self.destroy()

    def _close_app(self):
        if messagebox.askyesno("关闭", "是否关闭程序？", parent=self):
            self.app.quit_app()

    def _done(self):
        save_config(self.app.cfg)
        self.destroy()

    def _cancel(self):
        self.destroy()


# --------------------------------------------------------------------------- #
def main():
    # 单实例检测：若已有实例在运行，弹窗提示后退出
    if not acquire_instance_lock():
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            messagebox.showwarning(
                "桌面倒计时",
                "程序已经在运行中，请勿重复启动。",
                parent=root,
            )
        finally:
            root.destroy()
        sys.exit(0)
    try:
        CountdownApp().run()
    finally:
        release_instance_lock()


if __name__ == "__main__":
    main()