#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具  Beta 0.8
Python 3.8+ + tkinter + pystray + Pillow
"""

print("请勿关闭这个窗口(^_^)")      #这行代码在以py文件的方式运行时显示

import os
import sys
import threading
import queue
import subprocess
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog

import config
import dialogs
from config import (
    APP_VERSION, UI_FONT, BG_DARK, BG_PANEL, FG_MAIN, FG_SUB, ACCENT,
    OVERDUE, TRANSPARENT_KEY, GLASS_EDGE, BTN_HOVER, default_color_for,
)
from i18n import LanguageManager
from dialogs import (
    NameItemDialog, TimeItemDialog, AddItemDialog, SettingsWindow,
    AboutWindow, TextSettingsWindow, GuideWindow, ToolboxWindow,
)
from utils import (
    resource_dir, today, item_remaining,
    enable_dpi_awareness, enable_dwm_shadow, enable_rounded_corners,
    clamp_to_work_area, setup_logging, set_click_through, LOG, LOG_NAME,
)
from storage import (
    load_config, save_config, get_config_path, get_save_dir,
    migrate_legacy_config, get_log_dir,
    acquire_instance_lock, release_instance_lock,
)

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
# 进程检测（Beta 0.6 自动隐藏）
# --------------------------------------------------------------------------- #
def list_running_processes():
    """返回当前运行的进程名集合（小写，纯标准库实现，跨平台）。"""
    names = set()
    try:
        if sys.platform.startswith("win"):
            # Windows: tasklist /nh /fo csv，输出为 gbk 编码
            out = subprocess.run(
                ["tasklist", "/nh", "/fo", "csv"],
                capture_output=True, creationflags=0x08000000,
            ).stdout
            text = out.decode("gbk", errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('"') is False:
                    continue
                # CSV 第一列是进程名，带引号
                parts = line.split('","')
                if parts:
                    name = parts[0].lstrip('"').rstrip('"')
                    if name:
                        names.add(name.lower())
        else:
            # Linux / macOS: 遍历 /proc 或 ps
            if os.path.isdir("/proc"):
                for entry in os.listdir("/proc"):
                    if not entry.isdigit():
                        continue
                    try:
                        with open(os.path.join("/proc", entry, "comm"), "r") as f:
                            comm = f.read().strip()
                        if comm:
                            names.add(comm.lower())
                    except OSError:
                        continue
            else:
                out = subprocess.run(
                    ["ps", "-eo", "comm="], capture_output=True, text=True,
                ).stdout
                for line in out.splitlines():
                    comm = line.strip()
                    if comm:
                        names.add(comm.lower())
    except Exception:
        pass
    return names


def any_process_running(app_names):
    """app_names 为进程名列表（大小写不敏感），任一在运行返回 True。"""
    if not app_names:
        return False
    running = list_running_processes()
    targets = {n.lower() for n in app_names if n}
    return bool(running & targets)


# --------------------------------------------------------------------------- #
# 界面辅助
# --------------------------------------------------------------------------- #
def _sink_key(item):
    """排序键：剩余天数升序，已过期沉底（越早过期越靠后）。"""
    try:
        r = item_remaining(item)
    except Exception:
        return (2, 0)
    if r >= 0:
        return (0, r)
    return (1, -r)




# --------------------------------------------------------------------------- #
# 主应用
# --------------------------------------------------------------------------- #
class CountdownApp:
    def __init__(self):
        # 存档文件不存在即视为第一次启动
        self._first_launch = not os.path.exists(get_config_path())
        self.cfg = load_config()
        self._lang_mgr = LanguageManager.instance(self.cfg.get("language", "zh"))
        self._hidden = bool(self.cfg.get("hidden", False))
        self._auto_hidden = False  # Beta 0.6：标记是否由自动隐藏机制隐藏
        self._drag_anchor = None
        self.settings_win = None
        self.about_win = None
        self.text_settings_win = None
        self.guide_win = None
        self.toolbox_win = None
        self.right_menu = None
        self.tray_icon = None
        self._tray_queue = queue.Queue()
        self.row_name_labels = []
        self.row_days_labels = []
        self._purge_prompting = False
        self._purge_declined = set()

        self.root = tk.Tk()
        # 字体按平台可用性动态探测；高分屏按实际 DPI 校正 Tk 缩放
        global UI_FONT
        UI_FONT = config.set_ui_font(self.root)
        dialogs.UI_FONT = UI_FONT  # 弹窗模块同步运行时字体
        try:
            self.root.tk.call("tk", "scaling", self.root.winfo_fpixels("1i") / 72.0)
        except tk.TclError:
            pass
        self.root.title(self._lang_mgr.get("app_title"))
        self.root.overrideredirect(True)
        try:
            self.root.attributes("-topmost", bool(self.cfg.get("topmost", True)))
        except tk.TclError:
            pass

        self.bg = BG_DARK
        if sys.platform.startswith("win") and self.cfg.get("bg_mode") == "transparent":
            self.bg = TRANSPARENT_KEY
        self.root.configure(bg=self.bg)

        self._refresh_days_basis()
        self._build_ui()
        self._apply_bg_and_alpha()
        self._apply_dwm_shadow()
        self.rebuild_rows()
        self._restore_position()
        self._tick()
        self._start_tray()
        self.root.after(80, self._poll_tray_queue)
        self.root.after(2000, self._auto_hide_check)  # Beta 0.6

        # Windows 托盘通常可靠；Linux 上托盘后端常缺失，快捷键兜底常驻
        if not HAS_TRAY or not sys.platform.startswith("win"):
            self._bind_fallback_shortcuts()

        if self._is_locked():
            # 启动即处于锁定：整窗鼠标穿透（仅 Windows 生效）
            set_click_through(self.root, True)

        if self._hidden:
            self.root.withdraw()
        elif self._first_launch:
            # 第一次启动：先落盘配置（下次启动便不再算首次），再弹出引导
            save_config(self.cfg)
            self.root.after(400, self.open_guide)

    # ---------------- 基础 ---------------- #
    @property
    def lang(self):
        """取翻译文案的快捷方式：self.lang("key", **kwargs)。"""
        return self._lang_mgr.get

    def _refresh_days_basis(self):
        t = today().isoformat()
        changed = False
        for it in self.cfg.get("items", []):
            # 只在旧数据缺 base 时补默认值；已有基准日绝不覆盖，
            # 否则每次启动都会把「n 天后」重新续到今天，倒计时永远不减
            if it.get("mode") == "days" and not it.get("base"):
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
                    LOG.error("托盘回调错误: %s", exc)
        except queue.Empty:
            pass
        try:
            self.root.after(80, self._poll_tray_queue)
        except tk.TclError:
            pass

    # ---------------- 界面 ---------------- #
    def _build_ui(self):
        self.shell = tk.Frame(self.root, bg=GLASS_EDGE, bd=0, highlightthickness=0)
        self.shell.pack(fill="both", expand=True)
        self.container = tk.Frame(self.shell, bg=self.bg, bd=0, highlightthickness=0)
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        self.clock_label = tk.Label(
            self.container, text="", font=(UI_FONT, 9),
            fg=self.cfg.get("time_color") or FG_SUB, bg=self.bg, anchor="w",
        )
        self.clock_label.pack(fill="x", padx=15, pady=(8, 0))
        self.clock_label.bind("<Double-Button-1>", self._on_clock_double)
        self._bind_drag(self.clock_label)

        self.rows_frame = tk.Frame(self.container, bg=self.bg)
        self.rows_frame.pack(fill="both", expand=True, padx=15, pady=(6, 8))
        self.rows_frame.columnconfigure(0, weight=1)

        # 底板拖动（Beta 0.5）：点底板空白处也能拖窗。
        # 无底模式下这些区域在 Windows 为键色像素、点击直接穿透到下层，
        # 自然只在有底视觉时生效，不会与文字拖拽冲突
        for plate in (self.shell, self.container, self.rows_frame):
            plate.bind("<Button-1>", self._start_drag, add="+")
            plate.bind("<B1-Motion>", self._on_drag, add="+")
            plate.bind("<ButtonRelease-1>", self._end_drag, add="+")

        # 右键菜单绑在根窗口上，子控件事件会冒泡到这里
        self.root.bind("<Button-3>", self._show_right_menu)

    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._on_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_drag, add="+")
        for child in widget.winfo_children():
            self._bind_drag(child)

    # ---------------- 右键菜单 ---------------- #
    def _show_right_menu(self, event):
        # 锁定后不响应，解锁统一走托盘
        if self._is_locked():
            return
        self._build_right_menu()
        try:
            self.right_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.right_menu.grab_release()
            except tk.TclError:
                pass

    def _build_right_menu(self):
        if self.right_menu is not None:
            try:
                self.right_menu.destroy()
            except tk.TclError:
                pass
        fg = self.cfg.get("menu_text_color") or FG_MAIN
        m = tk.Menu(
            self.root, tearoff=0, bg=BG_PANEL, fg=fg,
            activebackground=BTN_HOVER, activeforeground=fg,
            bd=0, font=(UI_FONT, 10),
        )
        m.add_command(label=self.lang("add_countdown"), command=self._open_add_dialog)
        m.add_command(label=self.lang("settings"), command=self.open_settings)
        m.add_command(label=self.lang("guide"), command=self.open_guide)
        m.add_command(label=self.lang("toolbox"), command=self.open_toolbox)
        m.add_command(label=self.lang("about"), command=self.open_about)
        m.add_separator()
        m.add_command(label=self.lang("lock"), command=self._toggle_lock)
        m.add_command(label=self.lang("show_countdown") if self._hidden else self.lang("hide_countdown"),
                      command=self._toggle_visibility)
        m.add_separator()
        m.add_command(label=self.lang("quit"), command=self.quit_app)
        self.right_menu = m

    def _show_item_menu(self, event, item):
        """条目右键菜单：仅保留纯逻辑操作，避免 Toplevel 焦点死锁。"""
        if self._is_locked():
            return "break"
        fg = self.cfg.get("menu_text_color") or FG_MAIN
        m = tk.Menu(
            self.root, tearoff=0, bg=BG_PANEL, fg=fg,
            activebackground=BTN_HOVER, activeforeground=fg,
            bd=0, font=(UI_FONT, 10),
        )

        if item.get("mode") == "days":
            m.add_command(label=self.lang("reset_base_today"),
                          command=lambda: self._reset_item_base(item))

        # 加一个提示项，告诉用户怎么编辑
        m.add_command(label="双击条目可编辑", state="disabled")

        m.add_separator()
        m.add_command(label=self.lang("delete"), command=lambda: self.delete_item(item))

        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                m.grab_release()
            except tk.TclError:
                pass
            m.destroy()
        return "break"

    def _reset_item_base(self, item):
        item["base"] = today().isoformat()
        save_config(self.cfg)
        self.rebuild_rows()  # 加上这行，保证重新按天数排序
        self.refresh()

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
        # 窗口类型（Beta 0.5）：edge_plate 有边有底 / edge_only 有边无底 / none 无边无底
        style = self.cfg.get("win_style")
        if style not in ("edge_plate", "edge_only", "none"):
            style = "edge_plate"
        plate_color = self.cfg.get("plate_color") or BG_DARK
        edge_color = self.cfg.get("edge_color") or GLASS_EDGE
        # 逐像素透明（键色）仅 Windows 可用；其余平台无底样式回退为深色底板
        use_key = (sys.platform.startswith("win") and style in ("edge_only", "none"))
        self.bg = TRANSPARENT_KEY if use_key else plate_color
        self.root.configure(bg=self.bg)
        self._recolor(self.root)
        try:
            # 玻璃描边：无边无底时连同描边一起隐形；有边样式用自定义描边色
            if style == "none" and use_key:
                edge_bg = TRANSPARENT_KEY
            else:
                edge_bg = edge_color
            self.shell.configure(bg=edge_bg)
        except tk.TclError:
            pass
        try:
            alpha = float(self.cfg.get("alpha", 0.72))
        except (TypeError, ValueError):
            alpha = 0.72
        alpha = min(1.0, max(0.15, alpha))
        # Linux 极简模式：纯色底板不使用透明，半透明模式沿用上面的 alpha
        simple_solid = (
            not sys.platform.startswith("win")
            and sys.platform != "darwin"
            and bool(self.cfg.get("linux_simple_plate", False))
        )
        if simple_solid:
            alpha = 1.0
        elif self._is_locked():
            # 锁定后整体变淡，提示当前不可拖动 / 不可编辑
            alpha = max(0.15, alpha * 0.6)
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            pass

        if sys.platform.startswith("win"):
            try:
                self.root.attributes("-transparentcolor", self.bg if use_key else "")
            except tk.TclError:
                self.bg = BG_DARK
                try:
                    self.root.configure(bg=self.bg)
                except tk.TclError:
                    pass
                self._recolor(self.root)

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
        # 按剩余天数升序，已过期的排到底部
        items = sorted(self.cfg.get("items", []), key=_sink_key)

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
            name_lbl.bind("<Button-3>",
                          lambda e, it=item: self._show_item_menu(e, it))
            days_lbl.bind("<Button-3>",
                          lambda e, it=item: self._show_item_menu(e, it))

            self.row_name_labels.append((name_lbl, item))
            self.row_days_labels.append((days_lbl, item))

        if not items:
            hint = tk.Label(
                self.rows_frame, text=self.lang("empty_hint"),
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
                    self.lang("expired_title"),
                    self.lang("expired_purge_msg", names=names),
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
                    label.configure(text=self.lang("data_error"), fg=OVERDUE)
                except tk.TclError:
                    pass
                continue
            if r > 0:
                text = f"{r}{self.lang('day_unit')}"
            elif r == 0:
                text = self.lang("today")
            else:
                text = self.lang("expired")
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
        wd_keys = ("weekday_mon", "weekday_tue", "weekday_wed",
                   "weekday_thu", "weekday_fri", "weekday_sat", "weekday_sun")
        wd = self.lang(wd_keys[now.weekday()])
        s = self.lang("clock_format", date=now.strftime("%Y%m%d %H:%M:%S"), weekday=wd)
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
                # 编辑已有天数条目时保留原基准日，仅在使用「重置基准日」时刷新
                if not item.get("base"):
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
            h = self.root.winfo_reqheight()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
        except tk.TclError:
            return
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            x, y = sw - w - 40, 60
        # 多显示器：按窗口所在显示器的工作区钳制，副屏负坐标也能正确还原
        x, y = clamp_to_work_area(x, y, w, h, (sw, sh))
        self.root.geometry(f"+{x}+{y}")

    def _apply_dwm_shadow(self):
        if not sys.platform.startswith("win"):
            return
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return
        # 无边无底样式：关闭系统阴影与圆角，否则窗口矩形仍有一圈阴影轮廓，
        # 视觉上与"有边无底"没有区别
        enable = self.cfg.get("win_style") != "none"
        enable_dwm_shadow(self.root, enable)
        enable_rounded_corners(self.root, enable)

    # ---------------- 托盘 ---------------- #
    def _start_tray(self):
        if not HAS_TRAY:
            print("未安装 pystray / Pillow，无法启用系统托盘", file=sys.stderr)
            return
        img = self._load_tray_image()
        menu = pystray.Menu(
            # 锁定状态下，第一项固定显示“解锁窗口”
            pystray.MenuItem(
                lambda it: ("🔓 " + self.lang("unlock")) if self.cfg.get("locked")
                else self.lang("lock"),
                self._tray_toggle_lock,
                checked=lambda it: bool(self.cfg.get("locked", False)),
            ),
            pystray.MenuItem(self.lang("show_hide"), self._tray_toggle_show, default=True),
            pystray.MenuItem(self.lang("add_countdown"), self._tray_add),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.lang("topmost"), self._tray_toggle_topmost,
                             checked=lambda it: bool(self.cfg.get("topmost", True))),
            pystray.MenuItem(self.lang("settings"), self._tray_settings),
            pystray.MenuItem(self.lang("guide"), self._tray_guide),
            pystray.MenuItem(self.lang("toolbox"), self._tray_toolbox),
            pystray.MenuItem(self.lang("about"), self._tray_about),
            pystray.MenuItem(self.lang("export_log"), self._tray_export_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.lang("quit"), self._tray_quit),
        )
        # X11 后端的托盘标题按 latin-1 编码，中文会抛 UnicodeEncodeError，
        # 因此非 latin-1 可编码时退回英文名，保证托盘仍能启动
        title = self.lang("app_title")
        try:
            title.encode("latin-1")
        except UnicodeEncodeError:
            title = "Desktop Countdown"
        try:
            self.tray_icon = pystray.Icon("desktop_countdown", img, title, menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as exc:
            print("托盘启动失败:", exc, file=sys.stderr)
            # 托盘不可用时自动降级为快捷键操作
            self._bind_fallback_shortcuts()

    def _bind_fallback_shortcuts(self):
        """托盘不可用时的键盘降级：Ctrl+Shift+L 锁定/解锁，Ctrl+Shift+N 新增。"""
        self.root.bind("<Control-Shift-L>", lambda e: self._toggle_lock())
        self.root.bind("<Control-Shift-N>", lambda e: self._open_add_dialog())

    def _load_tray_image(self, size=64):
        here = resource_dir()
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

    def _tray_toggle_lock(self, icon=None, item=None):
        self._tray_queue.put(self._toggle_lock)

    def _tray_toggle_topmost(self, icon=None, item=None):
        self._tray_queue.put(self._toggle_topmost)

    def _tray_settings(self, icon=None, item=None):
        self._tray_queue.put(self.open_settings)

    def _tray_guide(self, icon=None, item=None):
        self._tray_queue.put(self.open_guide)

    def _tray_toolbox(self, icon=None, item=None):
        self._tray_queue.put(self.open_toolbox)

    def _tray_about(self, icon=None, item=None):
        self._tray_queue.put(self.open_about)

    def _tray_export_log(self, icon=None, item=None):
        self._tray_queue.put(self.export_log)

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
        # 用户手动切换：清除自动隐藏标记，避免被自动逻辑立即拉回
        self._auto_hidden = False
        if self._hidden:
            self._show_window()
        else:
            self._hide_window()

    def _hide_window(self, auto=False):
        try:
            self.cfg["x"] = self.root.winfo_x()
            self.cfg["y"] = self.root.winfo_y()
        except tk.TclError:
            pass
        self._hidden = True
        self._auto_hidden = bool(auto)
        self.cfg["hidden"] = True
        save_config(self.cfg)
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _show_window(self):
        self._hidden = False
        self._auto_hidden = False
        self.cfg["hidden"] = False
        save_config(self.cfg)
        try:
            self.root.deiconify()
            self.root.update()
            # 钳制回可见工作区，防止窗口停在屏幕外或被任务栏/面板遮挡
            self._restore_position()
            self.root.update()
            self._apply_bg_and_alpha()
            self.root.lift()
            # X11 下 deiconify 后立即 geometry 可能被吞，稍后补发一次
            self.root.after(60, self._restore_position)
            try:
                self.root.attributes("-topmost", bool(self.cfg.get("topmost", True)))
            except tk.TclError:
                pass
            self.root.focus_force()
        except tk.TclError:
            pass

    # ---------------- 自动隐藏（Beta 0.6） ---------------- #
    def _auto_hide_check(self):
        """轮询检测名单中的进程是否运行，据此自动隐藏/显示窗口。"""
        try:
            ah = self.cfg.get("auto_hide", {})
            apps = ah.get("apps", []) or []
            # 名单为空时无需遍历进程，直接跳过，避免周期性 CPU 峰值
            if ah.get("enabled") and apps:
                running = any_process_running(apps)
                if running and not self._hidden:
                    # 名单中有程序在运行 且 当前显示 → 自动隐藏
                    self._hide_window(auto=True)
                elif (not running) and self._hidden and self._auto_hidden:
                    # 名单中无程序运行 且 之前是被自动隐藏的 → 自动恢复显示
                    self._show_window()
        except Exception as exc:
            print("自动隐藏检测异常:", exc, file=sys.stderr)
        try:
            self.root.after(10000, self._auto_hide_check)
        except tk.TclError:
            pass

    def _toggle_lock(self):
        self.cfg["locked"] = not bool(self.cfg.get("locked", False))
        save_config(self.cfg)
        self._apply_bg_and_alpha()
        self.rebuild_rows()
        self.refresh()
        self._refresh_tray_menu()
        # 锁定时整窗鼠标穿透，解锁恢复（仅 Windows 生效，Linux 优雅跳过）
        set_click_through(self.root, self.cfg["locked"])

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
        self.guide_win = GuideWindow(self.root, self)

    def open_toolbox(self):
        if self.toolbox_win is not None and self.toolbox_win.winfo_exists():
            self.toolbox_win.lift()
            self.toolbox_win.focus_force()
            return
        self.toolbox_win = ToolboxWindow(self.root, self)

    def export_log(self, parent=None):
        """把当前日志复制到用户指定位置（Beta 0.8）。"""
        parent = parent or self.root
        log_dir = get_log_dir(self.cfg)
        src = os.path.join(log_dir, LOG_NAME)
        if not os.path.exists(src):
            # 找不到默认文件名时退而求其次：取日志目录中最新的 .log
            try:
                candidates = [os.path.join(log_dir, n)
                              for n in os.listdir(log_dir) if n.endswith(".log")]
                candidates.sort(key=os.path.getmtime, reverse=True)
                src = candidates[0] if candidates else ""
            except OSError:
                src = ""
        if not src:
            messagebox.showwarning(
                self.lang("prompt"),
                self.lang("export_log_failed", err=log_dir), parent=parent)
            return
        path = filedialog.asksaveasfilename(
            parent=parent,
            title=self.lang("export_log"),
            initialfile=os.path.basename(src),
            defaultextension=".log",
            filetypes=[("Log", "*.log"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            shutil.copy2(src, path)
        except OSError as exc:
            messagebox.showerror(
                self.lang("prompt"),
                self.lang("export_log_failed", err=exc), parent=parent)
            return
        messagebox.showinfo(
            self.lang("prompt"),
            self.lang("export_log_done", path=path), parent=parent)

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
        LOG.info("退出程序")
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
def main():
    # 高分屏：在创建任何窗口之前开启 DPI 感知
    enable_dpi_awareness()
    # 单实例检测：若已有实例在运行，弹窗提示后退出
    if not acquire_instance_lock():
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            _lm = LanguageManager.instance("zh")
            messagebox.showwarning(
                _lm.get("app_title"),
                _lm.get("already_running"),
                parent=root,
            )
        finally:
            root.destroy()
        sys.exit(0)
    try:
        # 旧版存档迁移：主目录的旧档复制到新存档位置（保留原文件）
        migrate_legacy_config()
        # 日志尽早初始化，之后发生的问题都能留痕
        _cfg = load_config()
        setup_logging(get_log_dir(_cfg))
        LOG.info("启动 %s | 平台=%s | 存档=%s | 日志=%s",
                 APP_VERSION, sys.platform, get_save_dir(), get_log_dir(_cfg))
        CountdownApp().run()
    finally:
        release_instance_lock()


if __name__ == "__main__":
    main()
