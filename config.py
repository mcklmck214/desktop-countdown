#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具 · 共享常量与界面基础件
配色、版本、链接、字体探测、按钮与窗口居中工具。
"""

import sys
import tkinter as tk


# --------------------------------------------------------------------------- #
# 版本与基础常量
# --------------------------------------------------------------------------- #
APP_VERSION = "Beta 0.8"
APP_NAME = "无名小工具"
AUTHOR_NAME = "四天不晚"
MAX_DAYS = 1000

BG_DARK = "#12161c"
BG_PANEL = "#1b2027"
FG_MAIN = "#e8eef5"
FG_SUB = "#8b9bab"
ACCENT = "#4fc3f7"
OVERDUE = "#ef5350"
ENTRY_BG = "#0e1218"
LINK_COLOR = "#5ec2ff"
TRANSPARENT_KEY = "#010203"
GLASS_EDGE = "#39434f"
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

BILI_URL = "https://space.bilibili.com/2061499488"
AFDIAN_URL = "https://ifdian.net/a/wmxgj"
QQ_FEEDBACK = ("823223052", "https://qm.qq.com/q/livvSfQFfG", "无名小工具反馈群")
QQ_CHAT = ("684287871", "https://qm.qq.com/q/1Q95hMYAxG", "无名小工具交流群")
GITHUB_URL = "https://github.com/mcklmck214/desktop-countdown"

WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")


# --------------------------------------------------------------------------- #
# 字体（运行时探测，高分屏 / 跨平台）
# --------------------------------------------------------------------------- #
if sys.platform.startswith("win"):
    UI_FONT = "Microsoft YaHei UI"
elif sys.platform == "darwin":
    UI_FONT = "PingFang SC"
else:
    UI_FONT = "Noto Sans CJK SC"

UI_FONT_FALLBACK = UI_FONT


def get_safe_font(root=None):
    """探测可用字体：微软雅黑 → 苹方 → Noto Sans CJK SC → 系统默认。

    PyInstaller 打包后 tkinter.font.families() 可能失败或返回空列表，
    因此全程 try/except，最差也返回平台默认字体，绝不返回空字符串。
    """
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei"):
        if name in families:
            return name
    try:
        import tkinter.font as tkfont
        family = tkfont.nametofont("TkDefaultFont", root=root).actual("family")
        if family:
            return family
    except Exception:
        pass
    return UI_FONT_FALLBACK


def set_ui_font(root=None):
    """探测并更新全局字体，返回字体名；dialogs 模块由主程序同步。"""
    global UI_FONT
    UI_FONT = get_safe_font(root)
    return UI_FONT


# --------------------------------------------------------------------------- #
# 界面辅助
# --------------------------------------------------------------------------- #
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
