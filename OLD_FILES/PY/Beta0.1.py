#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面透明倒计时  (Python 3.12 + tkinter)

功能
  · 主窗口无边框、置顶、可调透明度；Windows 下还可让背景完全透明（只剩文字浮在桌面上）
  · 右键菜单打开独立的设置窗口，可增删改任意多个倒计时
  · 右键菜单含「使用引导」，新手可快速了解全部操作
  · 右键菜单含「关于」，可查看版本、作者与反馈/交流群信息
  · 首次启动时自动弹出引导窗口
  · 自动读取系统时间，每秒刷新
  · 每次启动自动刷新：所有「n 天后」条目以启动当天为基准重新计算
  · 右键菜单可「固定窗口」，固定后无法再拖动；锁标志显示在每个倒计时名称后面
  · 双击主窗口中的条目名称 → 直接重命名
  · 单个倒计时最大 1000 天
  · 两种方式：n 天后 / yyyy年mm月dd日

操作
  · 左键拖动        —— 移动窗口（未固定时）
  · 双击条目名称    —— 重命名该倒计时
  · 右键            —— 菜单（使用引导 / 设置 / 刷新 / 固定窗口 / 关于 / 退出）
  · Ctrl + 左键     —— 同右键

配置文件：~/.desktop_countdown.json
"""

import json
import os
import re
import sys
import webbrowser
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
MAX_DAYS = 1000
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".desktop_countdown.json")

BG_DARK = "#12161c"     # 半透明模式下的背景
BG_PANEL = "#1b2027"    # 设置窗口背景
FG_MAIN = "#e8eef5"
FG_SUB = "#8b9bab"
ACCENT = "#4fc3f7"
WARN = "#ffb74d"
OVERDUE = "#ef5350"
ENTRY_BG = "#0e1218"

# 右键菜单配色（浅色，保证在任何桌面背景下都清晰可辨）
MENU_BG = "#f3f5f8"
MENU_FG = "#1b2027"
MENU_ACTIVE_BG = "#2f6fb5"
MENU_ACTIVE_FG = "#ffffff"
MENU_DISABLED_FG = "#9aa7b4"

LOCK_MARK = "🔒"       # 锁定标志，显示在倒计时名称后面

LINK_COLOR = "#5ec2ff"  # 「关于」窗口中可点击文字的颜色

# 「关于」窗口中的链接 / 联系方式
BILI_URL = "https://space.bilibili.com/2061499488"
EMAIL = "mcklmck214@outlook.com"
QQ_FEEDBACK = ("823223052", "https://qm.qq.com/q/livvSfQFfG/", "无名小工具反馈群")
QQ_CHAT = ("684287871", "https://qm.qq.com/q/1Q95hMYAxG/", "无名小工具交流群")
QQ_COLLECT = ("136476657", "https://qm.qq.com/q/twudn725CU/", "无名小工具征集群")

if sys.platform.startswith("win"):
    UI_FONT = "Microsoft YaHei UI"
elif sys.platform == "darwin":
    UI_FONT = "PingFang SC"
else:
    UI_FONT = "Noto Sans CJK SC"

WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

TRANSPARENT_KEY = "#010203"   # Windows 透明色键（不要和界面里的颜色重复）


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def today() -> date:
    """当前系统日期（自动调取系统时间）。"""
    return datetime.now().date()


def parse_date_str(text: str) -> date:
    """解析 yyyy年mm月dd日 / yyyy-mm-dd / yyyy/mm/dd / yyyymmdd。"""
    s = text.strip()
    if not s:
        raise ValueError("请输入日期")
    m = re.match(r"^(\d{4})\s*\D+\s*(\d{1,2})\s*\D+\s*(\d{1,2})\s*\D*$", s)
    if m is None:
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m is None:
        raise ValueError("日期格式应为 yyyy年mm月dd日（也支持 2026-10-11）")
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise ValueError("日期不存在，请检查年月日") from None


def item_target(item: dict) -> date:
    """计算某个倒计时条目的目标日期。"""
    if item.get("mode") == "date":
        return date.fromisoformat(item["date"])
    base = date.fromisoformat(item.get("base") or today().isoformat())
    return base + timedelta(days=int(item.get("days", 0)))


def item_remaining(item: dict, t: date | None = None) -> int:
    """剩余天数（负数表示已过期）。"""
    return (item_target(item) - (t or today())).days


def item_rule_text(item: dict) -> str:
    """条目规则的文字描述。"""
    if item.get("mode") == "date":
        d = date.fromisoformat(item["date"])
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"
    return f"{int(item.get('days', 0))} 天后"


# --------------------------------------------------------------------------- #
# 配置读写
# --------------------------------------------------------------------------- #
def default_config() -> dict:
    t = today()
    try:
        new_year = date(t.year + 1, 1, 1)
    except ValueError:
        new_year = t + timedelta(days=365)
    return {
        "alpha": 0.90,
        "font_size": 14,
        "transparent_bg": True,
        "locked": False,          # 窗口是否固定
        "guide_shown": False,     # 是否已经展示过首次启动引导
        "x": None,
        "y": None,
        "items": [{"name": "元旦", "mode": "date", "date": new_year.isoformat()}],
    }


def load_config() -> dict:
    cfg = default_config()
    if not os.path.exists(CONFIG_PATH):
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    for key in ("alpha", "font_size", "transparent_bg", "locked",
                "guide_shown", "x", "y"):
        if key in data:
            cfg[key] = data[key]
    if isinstance(data.get("items"), list):
        cfg["items"] = [
            it for it in data["items"]
            if isinstance(it, dict) and it.get("name") and it.get("mode") in ("days", "date")
        ]
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print("保存配置失败:", exc, file=sys.stderr)


# --------------------------------------------------------------------------- #
# 主窗口
# --------------------------------------------------------------------------- #
class CountdownApp:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.settings = None
        self.guide = None
        self.about = None
        self._drag_anchor = None
        self.bg = BG_DARK
        self.row_labels: list[tuple[tk.Label, dict]] = []

        self.root = tk.Tk()
        self.root.title("桌面倒计时")
        self.root.overrideredirect(True)                 # 无边框
        try:
            self.root.attributes("-topmost", True)       # 置顶
        except tk.TclError:
            pass
        self.root.configure(bg=self.bg)

        self.locked_var = tk.BooleanVar(value=bool(self.cfg.get("locked", False)))

        self._refresh_items_on_start()                   # 启动时刷新所有「n 天后」
        self._build_ui()
        self.apply_style()
        self.rebuild_rows()
        self._restore_position()
        self._tick()                                     # 启动刷新循环

        # 首次启动检测：稍后弹出引导，避免主窗口还没绘制好
        self.root.after(200, self._maybe_show_first_guide)

    # ---------------- 首次启动引导 ---------------- #
    def _maybe_show_first_guide(self) -> None:
        """如果配置中未记录已展示过引导，则自动打开引导并写入标记。"""
        if self.cfg.get("guide_shown"):
            return
        self.cfg["guide_shown"] = True
        save_config(self.cfg)
        self.open_guide()

    # ---------------- 启动刷新 ---------------- #
    def _refresh_items_on_start(self) -> None:
        """
        每次启动时，把所有「n 天后」条目的基准日期重置为今天，
        这样它们的剩余天数永远是「从启动当天算起的 n 天」。
        「指定日期」条目本身是绝对日期，不受影响。
        """
        t = today().isoformat()
        changed = False
        for it in self.cfg.get("items", []):
            if it.get("mode") == "days" and it.get("base") != t:
                it["base"] = t
                changed = True
        if changed:
            save_config(self.cfg)

    # ---------------- 界面搭建 ---------------- #
    def _build_ui(self) -> None:
        self.container = tk.Frame(self.root, bg=self.bg, bd=0, highlightthickness=0)
        self.container.pack(fill="both", expand=True, padx=16, pady=12)

        self.clock_label = tk.Label(
            self.container, text="", font=(UI_FONT, 10),
            fg=FG_SUB, bg=self.bg, anchor="w",
        )
        self.clock_label.pack(fill="x")

        self.rows_frame = tk.Frame(self.container, bg=self.bg)
        self.rows_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.rows_frame.columnconfigure(0, weight=1)

        # ---- 右键菜单（浅色配色，确保清晰可辨） ----
        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=MENU_BG,
            fg=MENU_FG,
            activebackground=MENU_ACTIVE_BG,
            activeforeground=MENU_ACTIVE_FG,
            disabledforeground=MENU_DISABLED_FG,
            relief="flat",
            bd=0,
            font=(UI_FONT, 10),
        )
        self.menu.add_command(label="使用引导", command=self.open_guide)
        self.menu.add_separator()
        self.menu.add_command(label="设置…", command=self.open_settings)
        self.menu.add_command(label="刷新", command=self.refresh_all)
        self.menu.add_separator()
        self.menu.add_checkbutton(
            label="固定窗口", variable=self.locked_var, command=self._toggle_lock,
            selectcolor=MENU_BG,
        )
        self.menu.add_separator()
        self.menu.add_command(label="关于", command=self.open_about)
        self.menu.add_command(label="退出", command=self.quit)

        self.root.bind("<Button-3>", self._popup_menu)
        self.root.bind("<Control-Button-1>", self._popup_menu)

        self._bind_drag(self.root)

    def _bind_drag(self, widget: tk.Misc) -> None:
        widget.bind("<Button-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._on_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_drag, add="+")
        widget.bind("<Button-3>", self._popup_menu, add="+")
        widget.bind("<Control-Button-1>", self._popup_menu, add="+")
        for child in widget.winfo_children():
            self._bind_drag(child)

    # ---------------- 固定 / 拖动 ---------------- #
    def _toggle_lock(self) -> None:
        """切换窗口固定状态并持久化；锁标志显示在名称后面。"""
        self.cfg["locked"] = bool(self.locked_var.get())
        save_config(self.cfg)
        self.rebuild_rows()     # 重建以刷新名称后的锁标志
        self.refresh()

    def _start_drag(self, event: tk.Event) -> None:
        if self.locked_var.get():          # 已固定，禁止拖动
            self._drag_anchor = None
            return
        self._drag_anchor = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_anchor is None or self.locked_var.get():
            return
        dx, dy = self._drag_anchor
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _end_drag(self, event: tk.Event) -> None:
        if self._drag_anchor is None:
            return
        self._drag_anchor = None
        if self.locked_var.get():
            return
        self.cfg["x"] = self.root.winfo_x()
        self.cfg["y"] = self.root.winfo_y()
        save_config(self.cfg)

    # ---------------- 透明与外观 ---------------- #
    def apply_style(self) -> None:
        alpha = float(self.cfg.get("alpha", 0.9))
        alpha = min(1.0, max(0.15, alpha))
        self.cfg["alpha"] = alpha

        use_key = bool(self.cfg.get("transparent_bg", True)) and sys.platform.startswith("win")
        self.bg = TRANSPARENT_KEY if use_key else BG_DARK

        try:
            self.root.attributes("-alpha", alpha)          # 整体透明度
        except tk.TclError:
            pass

        if sys.platform.startswith("win"):
            try:
                self.root.attributes("-transparentcolor", self.bg if use_key else "")
            except tk.TclError:
                self.bg = BG_DARK

        self.root.configure(bg=self.bg)
        self._recolor(self.root)

    def _recolor(self, widget: tk.Misc) -> None:
        """把整棵控件树的背景刷成当前背景色（跳过其它顶层窗口）。"""
        if isinstance(widget, tk.Toplevel):
            return
        try:
            widget.configure(bg=self.bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._recolor(child)

    # ---------------- 名称显示（含锁标志） ---------------- #
    def _display_name(self, item: dict) -> str:
        """倒计时名称的显示文本：锁定时在名称后面追加锁标志。"""
        name = str(item.get("name", ""))
        if self.locked_var.get():
            name = f"{name} {LOCK_MARK}"
        return name

    # ---------------- 列表渲染 ---------------- #
    def rebuild_rows(self) -> None:
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.row_labels.clear()

        size = int(self.cfg.get("font_size", 14))
        for i, item in enumerate(self.cfg.get("items", [])):
            name_lbl = tk.Label(
                self.rows_frame, text=self._display_name(item),
                font=(UI_FONT, size), fg=FG_MAIN, bg=self.bg, anchor="w",
                cursor="hand2",   # 鼠标悬停变成手型，提示可双击
            )
            name_lbl.grid(row=i, column=0, sticky="w", pady=1)

            days_lbl = tk.Label(
                self.rows_frame, text="",
                font=(UI_FONT, size, "bold"), fg=ACCENT, bg=self.bg, anchor="e",
                cursor="hand2",
            )
            days_lbl.grid(row=i, column=1, sticky="e", padx=(24, 0), pady=1)

            for w in (name_lbl, days_lbl):
                self._bind_drag(w)
                # 双击 → 重命名
                w.bind("<Double-Button-1>",
                       lambda e, it=item: self._rename_item(it), add="+")
            self.row_labels.append((days_lbl, item))

        if not self.cfg.get("items"):
            hint_text = "右键 → 设置… 添加倒计时"
            if self.locked_var.get():
                hint_text = f"{hint_text} {LOCK_MARK}"
            hint = tk.Label(
                self.rows_frame, text=hint_text,
                font=(UI_FONT, 11), fg=FG_SUB, bg=self.bg, anchor="w",
            )
            hint.grid(row=0, column=0, columnspan=2, sticky="w")
            self._bind_drag(hint)

    def refresh(self) -> None:
        t = today()
        for label, item in self.row_labels:
            try:
                r = item_remaining(item, t)
            except Exception:
                label.configure(text="数据错误", fg=OVERDUE)
                continue
            if r > 0:
                text = f"{r} 天"
                color = WARN if r <= 7 else ACCENT
            elif r == 0:
                text = "就是今天 🎉"
                color = WARN
            else:
                text = f"已过 {-r} 天"
                color = OVERDUE
            label.configure(text=text, fg=color)

    def refresh_all(self) -> None:
        """手动刷新：重新以今天为基准计算「n 天后」条目，并重建显示。"""
        self._refresh_items_on_start()
        self.rebuild_rows()
        self.refresh()

    def _clock_text(self) -> str:
        """时钟行只显示日期时间和星期。"""
        now = datetime.now()
        return f"{now.strftime('%Y-%m-%d %H:%M:%S')}  {WEEKDAYS[now.weekday()]}"

    def _tick(self) -> None:
        self.clock_label.configure(text=self._clock_text())
        self.refresh()
        self.root.after(1000, self._tick)

    # ---------------- 重命名 ---------------- #
    def _rename_item(self, item: dict) -> None:
        """双击条目时弹出对话框修改名称。"""
        old_name = item.get("name", "")
        new_name = RenameDialog(self.root, old_name).result
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        item["name"] = new_name
        save_config(self.cfg)
        self.rebuild_rows()     # 重建以刷新显示文字
        self.refresh()

    # ---------------- 位置 ---------------- #
    def _restore_position(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            x, y = sw - w - 40, 60
        x = max(0, min(int(x), max(0, sw - 60)))
        y = max(0, min(int(y), max(0, sh - 60)))
        self.root.geometry(f"+{x}+{y}")

    # ---------------- 菜单动作 ---------------- #
    def _popup_menu(self, event: tk.Event) -> str:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
        return "break"

    def open_guide(self) -> None:
        """打开使用引导窗口。"""
        if self.guide is not None and self.guide.winfo_exists():
            self.guide.lift()
            self.guide.focus_force()
            return
        self.guide = GuideWindow(self.root, self)

    def open_about(self) -> None:
        """打开「关于」窗口。"""
        if self.about is not None and self.about.winfo_exists():
            self.about.lift()
            self.about.focus_force()
            return
        self.about = AboutWindow(self.root, self)

    def open_settings(self) -> None:
        if self.settings is not None and self.settings.winfo_exists():
            self.settings.lift()
            self.settings.focus_force()
            return
        self.settings = SettingsWindow(self)

    def quit(self) -> None:
        self.cfg["x"] = self.root.winfo_x()
        self.cfg["y"] = self.root.winfo_y()
        save_config(self.cfg)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# --------------------------------------------------------------------------- #
# 使用引导窗口
# --------------------------------------------------------------------------- #
class GuideWindow(tk.Toplevel):
    """展示操作说明的新手引导窗口。"""

    def __init__(self, parent: tk.Misc, app: CountdownApp) -> None:
        super().__init__(parent)
        self.app = app

        self.title("使用引导")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=(14, 10))

        # 用只读 Text 承载引导文字，便于分段排版
        # 高度先给个初始值，内容填充后再按实际行数调整
        self.text = tk.Text(
            body, width=48, height=10, wrap="word",
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            highlightthickness=0, cursor="arrow",
            font=(UI_FONT, 10), spacing1=1, spacing3=1,
        )
        self.text.pack(fill="both", expand=True)

        # 文本样式
        self.text.tag_configure(
            "h", font=(UI_FONT, 11, "bold"), foreground=ACCENT,
            spacing1=10, spacing3=4,
        )
        self.text.tag_configure(
            "b", font=(UI_FONT, 10), foreground=FG_MAIN, lmargin1=14, lmargin2=14,
        )
        self.text.tag_configure(
            "k", font=(UI_FONT, 10, "bold"), foreground=WARN,
        )
        self.text.tag_configure(
            "s", font=(UI_FONT, 10), foreground=FG_SUB, lmargin1=14, lmargin2=14,
            spacing3=2,
        )

        self._fill_content()
        self.text.configure(state="disabled")   # 只读
        self._fit_height()                      # 按内容自适应高度

        # 关闭按钮
        bottom = tk.Frame(self, bg=BG_PANEL)
        bottom.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(
            bottom, text="知道了", command=self.destroy,
            bg="#2f6fb5", fg="#ffffff", activebackground="#3b82d1",
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=16, pady=5, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self._center(parent)

    def _fit_height(self) -> None:
        """
        根据 Text 中实际内容计算需要显示的行数，避免内容被截断。
        同时限制最大行数，防止内容过多时窗口超出屏幕。
        """
        self.text.update_idletasks()
        # 'end-1c' 是最后一个字符之前的位置，得到的是“行号.列号”
        last_index = self.text.index("end-1c")
        try:
            total_lines = int(last_index.split(".")[0])
        except (ValueError, IndexError):
            total_lines = 24
        # 多加 1 行余量，避免紧贴边框；最多 40 行
        height = max(12, min(total_lines + 1, 40))
        self.text.configure(height=height)
        self.update_idletasks()

    def _fill_content(self) -> None:
        add = self.text.insert

        add("end", "① 移动和固定\n", "h")
        add("end", "· 左键拖动窗口 —— 放到任意位置\n", "b")
        add("end", "· 右键 → 固定窗口 —— 锁住位置，防止误拖\n", "b")
        add("end", "  固定后每个倒计时名称后面会出现 ", "b")
        add("end", "🔒\n", "k")

        add("end", "② 添加倒计时\n", "h")
        add("end", "· 右键 → 设置… 打开设置窗口\n", "b")
        add("end", "· 填写名称，选择「n 天后」或「指定日期」\n", "b")
        add("end", "· 点「添加到列表」，最后「保存并关闭」\n", "b")

        add("end", "③ 两种倒计时方式\n", "h")
        add("end", "· n 天后 —— 以启动当天为基准，每次打开自动刷新\n", "b")
        add("end", "· 指定日期 —— 固定在某个绝对日期，格式 2026年10月11日\n", "b")

        add("end", "④ 快速修改名称\n", "h")
        add("end", "· 直接双击主窗口中倒计时名称 —— 立刻重命名\n", "b")
        add("end", "· 在设置窗口中双击列表项 —— 同样可以改名\n", "b")

        add("end", "⑤ 外观调整\n", "h")
        add("end", "· 透明度滑块 —— 实时调整主窗口通透程度\n", "b")
        add("end", "· 字号 —— 主窗口文字大小（8 ~ 48）\n", "b")
        add("end", "· 背景完全透明 —— Windows 下仅显示文字\n", "b")

        add("end", "小提示\n", "h")
        add("end", f"· 单个倒计时最长 {MAX_DAYS} 天\n", "s")
        add("end", "· 所有设置自动保存在 ~/.desktop_countdown.json\n", "s")
        add("end", "· 配置文件中记录了每个条目的名称、方式与目标日期\n", "s")
        add("end", "· 右键 → 关于 可查看版本与反馈群信息\n", "s")

    def _center(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
        except tk.TclError:
            px = py = 100
        x = px - w - 24 if px - w - 24 > 10 else px + parent.winfo_width() + 24
        y = py
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 10))
        self.geometry(f"+{x}+{y}")


# --------------------------------------------------------------------------- #
# 关于窗口
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 关于窗口
# --------------------------------------------------------------------------- #
class AboutWindow(tk.Toplevel):
    """
    「关于」窗口。

    带下划线的文字都可以点击：
      · 数字 / 邮箱 —— 点击复制到剪贴板
      · 链接       —— 点击调用系统浏览器打开
    """

    def __init__(self, parent: tk.Misc, app: CountdownApp) -> None:
        super().__init__(parent)
        self.app = app
        self._link_seq = 0
        self._flash_job = None

        self.title("关于")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=(14, 6))

        self.text = tk.Text(
            body, width=70, height=10, wrap="word",
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            highlightthickness=0, cursor="arrow", insertwidth=0,
            font=(UI_FONT, 10), spacing1=1, spacing3=1,
        )
        self.text.pack(fill="both", expand=True)

        self._configure_tags()
        self._fill_content()
        self.text.configure(state="normal")
        # 只读：拦掉所有按键，避免内容被改写
        self.text.bind("<Key>", lambda e: "break")
        self.text.bind("<<Paste>>", lambda e: "break")
        self._fit_height()

        # 状态提示（复制反馈）
        self.status = tk.Label(
            self, text="", bg=BG_PANEL, fg=ACCENT, anchor="w",
            font=(UI_FONT, 9),
        )
        self.status.pack(fill="x", padx=16)

        bottom = tk.Frame(self, bg=BG_PANEL)
        bottom.pack(fill="x", padx=16, pady=(6, 14))
        tk.Button(
            bottom, text="关闭", command=self.destroy,
            bg="#2f6fb5", fg="#ffffff", activebackground="#3b82d1",
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=16, pady=5, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self._center(parent)

    # ---------------- 样式 ---------------- #
    def _configure_tags(self) -> None:
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
        t.tag_configure("note", font=(UI_FONT, 9), foreground=FG_SUB,
                        spacing1=10, spacing3=2)
        t.tag_configure("hint", font=(UI_FONT, 9), foreground=FG_SUB,
                        spacing1=12)

    # ---------------- 内容 ---------------- #
    def _insert_link(self, text: str, mode: str, payload: str) -> None:
        """插入一段可点击文字。mode 为 'copy'（复制）或 'open'（浏览器打开）。"""
        self._link_seq += 1
        tag = f"lnk{self._link_seq}"
        self.text.tag_configure(tag, foreground=LINK_COLOR, underline=True)
        self.text.tag_bind(
            tag, "<Button-1>",
            lambda e, m=mode, p=payload: self._on_link(m, p),
        )
        self.text.tag_bind(
            tag, "<Enter>",
            lambda e: self.text.configure(cursor="hand2"),
        )
        self.text.tag_bind(
            tag, "<Leave>",
            lambda e: self.text.configure(cursor="arrow"),
        )
        self.text.insert("end", text, tag)
        self.text.tag_raise(tag)   # 保证链接颜色 / 下划线优先级最高

    def _fill_content(self) -> None:
        add = self.text.insert

        add("end", "无名小工具\n", "title")
        add("end", "Beta 0.1\n", "ver")

        add("end", "更新日志：从头开始！\n", "h")

        add("end", "作者：", "b")
        self._insert_link("四天不晚", "open", BILI_URL)
        add("end", "\n", "b")
        add("end", "只是一个学牲罢了。\n", "s")

        add("end", "注：本程序部分为 AI 辅助编写。\n", "note")

        # ---- 反馈群 / 交流群 ----
        for label, (number, url, name) in (
            ("反馈群：", QQ_FEEDBACK),
            ("交流群：", QQ_CHAT),
        ):
            add("end", label, "b")
            self._insert_link(number, "copy", number)
            add("end", "　", "b")
            self._insert_link(f"点击加入群聊【{name}】", "open", url)
            add("end", "\n", "b")

        # ---- 征集 ----
        add("end", "征集程序名称、图标\n", "h")
        add("end", "请加群：", "b")
        number, url, name = QQ_COLLECT
        self._insert_link(number, "copy", number)
        add("end", "　", "b")
        self._insert_link(f"点击加入群聊【{name}】", "open", url)
        add("end", "\n", "b")

        add("end", "或发送至邮箱：", "b")
        self._insert_link(EMAIL, "copy", EMAIL)
        add("end", "\n", "b")

        add("end", "要求：没啥要求，只需要备注你的 B 站名或 UID 就好了。\n", "s")

    def _fit_height(self) -> None:
        """按内容行数自适应高度，避免被截断。"""
        self.text.update_idletasks()
        try:
            total_lines = int(self.text.index("end-1c").split(".")[0])
        except (ValueError, IndexError):
            total_lines = 20
        self.text.configure(height=max(10, min(total_lines + 1, 40)))
        self.update_idletasks()

    # ---------------- 点击行为 ---------------- #
    def _on_link(self, mode: str, payload: str) -> None:
        if mode == "copy":
            try:
                self.clipboard_clear()
                self.clipboard_append(payload)
                self.update_idletasks()
                self._flash(f"已复制：{payload}")
            except tk.TclError:
                self._flash("复制失败，请手动选择文本复制")
        else:
            try:
                webbrowser.open(payload)
                self._flash("已在浏览器中打开")
            except Exception:
                self._flash("无法打开浏览器，请手动访问：" + payload)

    def _flash(self, message: str, ms: int = 2500) -> None:
        """在状态栏短暂显示一条提示。"""
        self.status.configure(text=message)
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except tk.TclError:
                pass
        self._flash_job = self.after(
            ms, lambda: self.status.configure(text="")
        )

    # ---------------- 居中 ---------------- #
    def _center(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw = parent.winfo_width()
        except tk.TclError:
            px = py = 100
            pw = 0
        x = px - w - 24
        if x < 10:
            x = px + pw + 24
        y = py
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 10))
        self.geometry(f"+{x}+{y}")


# --------------------------------------------------------------------------- #
# 重命名对话框（自绘，风格与主界面统一）
# --------------------------------------------------------------------------- #
class RenameDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, initial: str) -> None:
        super().__init__(parent)
        self.result: str | None = None

        self.title("重命名倒计时")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        # 内容
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(body, text="新的名称：", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).pack(anchor="w")

        self.var = tk.StringVar(value=initial)
        entry = tk.Entry(
            body, textvariable=self.var, bg=ENTRY_BG, fg=FG_MAIN,
            insertbackground=FG_MAIN, relief="flat",
            font=(UI_FONT, 11), width=24,
        )
        entry.pack(fill="x", pady=(4, 10))
        entry.focus_set()
        entry.select_range(0, "end")
        entry.icursor("end")

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x")

        tk.Button(
            btns, text="取消", command=self._cancel,
            bg="#2a323c", fg=FG_MAIN, activebackground="#3a4550",
            activeforeground=FG_MAIN, relief="flat", bd=0,
            padx=14, pady=4, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            btns, text="确定", command=self._ok,
            bg="#2f6fb5", fg="#ffffff", activebackground="#3b82d1",
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=14, pady=4, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._center(parent)
        self.grab_set()
        self.wait_window(self)

    def _center(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
        except tk.TclError:
            px = py = 100
        x = px + 20
        y = py + 20
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 10))
        self.geometry(f"+{x}+{y}")

    def _ok(self) -> None:
        self.result = self.var.get()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


# --------------------------------------------------------------------------- #
# 独立设置窗口
# --------------------------------------------------------------------------- #
class SettingsWindow(tk.Toplevel):
    def __init__(self, app: CountdownApp) -> None:
        super().__init__(app.root)
        self.app = app
        self.items = [dict(it) for it in app.cfg.get("items", [])]
        self.editing_index: int | None = None

        self.title("倒计时设置")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(app.root)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build()
        self._refresh_list()
        self._new_item()
        self._place_near_main()

    # ---------------- 布局 ---------------- #
    def _build(self) -> None:
        # ---- 列表 ----
        box = tk.Frame(self, bg=BG_PANEL)
        box.pack(fill="x", padx=12, pady=(12, 0))

        tk.Label(box, text="倒计时列表", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10, "bold"), anchor="w").pack(fill="x")

        self.listbox = tk.Listbox(
            box, height=8, bg=ENTRY_BG, fg=FG_MAIN,
            selectbackground="#2f6fb5", selectforeground="#ffffff",
            font=(UI_FONT, 10), bd=0, highlightthickness=1,
            highlightbackground="#2b3540", activestyle="none",
            exportselection=False,
        )
        self.listbox.pack(fill="x", pady=(4, 6))
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        # 双击列表项也可以直接重命名
        self.listbox.bind("<Double-Button-1>", lambda e: self._rename_from_list())

        bar = tk.Frame(box, bg=BG_PANEL)
        bar.pack(fill="x")
        for text, cmd in (
            ("新建", self._new_item),
            ("删除", self._delete_item),
            ("上移", lambda: self._move(-1)),
            ("下移", lambda: self._move(1)),
        ):
            tk.Button(
                bar, text=text, command=cmd, bg="#2a323c", fg=FG_MAIN,
                activebackground="#3a4550", activeforeground=FG_MAIN,
                relief="flat", bd=0, padx=10, pady=3,
                font=(UI_FONT, 9), cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        # ---- 表单 ----
        form = tk.Frame(self, bg=BG_PANEL)
        form.pack(fill="x", padx=12, pady=(10, 0))
        form.columnconfigure(1, weight=1)

        tk.Label(form, text="名称", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.name_var, bg=ENTRY_BG, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat",
                 font=(UI_FONT, 10)).grid(row=0, column=1, columnspan=3,
                                          sticky="ew", pady=4, padx=(8, 0))

        tk.Label(form, text="方式", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="days")
        mode_box = tk.Frame(form, bg=BG_PANEL)
        mode_box.grid(row=1, column=1, columnspan=3, sticky="w", padx=(8, 0))
        for text, val in (("n 天后", "days"), ("指定日期", "date")):
            tk.Radiobutton(
                mode_box, text=text, value=val, variable=self.mode_var,
                command=self._update_mode_state, bg=BG_PANEL, fg=FG_MAIN,
                selectcolor=ENTRY_BG, activebackground=BG_PANEL,
                activeforeground=FG_MAIN, font=(UI_FONT, 10),
                highlightthickness=0, bd=0,
            ).pack(side="left", padx=(0, 12))

        tk.Label(form, text="天数", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        self.days_var = tk.StringVar(value="30")
        self.days_entry = tk.Entry(
            form, textvariable=self.days_var, bg=ENTRY_BG, fg=FG_MAIN,
            disabledbackground="#171c22", disabledforeground="#5a6773",
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10), width=8,
        )
        self.days_entry.grid(row=2, column=1, sticky="w", pady=4, padx=(8, 0))
        tk.Label(form, text=f"（1 ~ {MAX_DAYS}）", bg=BG_PANEL, fg=FG_SUB,
                 font=(UI_FONT, 9)).grid(row=2, column=2, sticky="w")

        tk.Label(form, text="日期", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=3, column=0, sticky="w", pady=4)
        self.date_var = tk.StringVar()
        self.date_entry = tk.Entry(
            form, textvariable=self.date_var, bg=ENTRY_BG, fg=FG_MAIN,
            disabledbackground="#171c22", disabledforeground="#5a6773",
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10),
        )
        self.date_entry.grid(row=3, column=1, columnspan=2, sticky="ew",
                             pady=4, padx=(8, 0))
        tk.Label(form, text="如 2026年10月11日", bg=BG_PANEL, fg=FG_SUB,
                 font=(UI_FONT, 9)).grid(row=3, column=3, sticky="w", padx=(6, 0))

        self.apply_btn = tk.Button(
            self, text="添加到列表", command=self._apply_item,
            bg="#2f6fb5", fg="#ffffff", activebackground="#3b82d1",
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=14, pady=5, font=(UI_FONT, 10), cursor="hand2",
        )
        self.apply_btn.pack(anchor="e", padx=12, pady=(8, 0))

        # ---- 外观 ----
        look = tk.Frame(self, bg=BG_PANEL)
        look.pack(fill="x", padx=12, pady=(12, 0))
        look.columnconfigure(1, weight=1)

        tk.Label(look, text="透明度", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w")
        self.alpha_var = tk.DoubleVar(value=float(self.app.cfg.get("alpha", 0.9)))
        tk.Scale(
            look, from_=0.15, to=1.0, resolution=0.05, orient="horizontal",
            variable=self.alpha_var, command=self._on_alpha,
            bg=BG_PANEL, fg=FG_MAIN, troughcolor=ENTRY_BG,
            highlightthickness=0, bd=0, length=200, font=(UI_FONT, 9),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        tk.Label(look, text="字号", bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.font_var = tk.IntVar(value=int(self.app.cfg.get("font_size", 14)))
        tk.Spinbox(
            look, from_=8, to=48, textvariable=self.font_var, width=5,
            bg=ENTRY_BG, fg=FG_MAIN, buttonbackground="#2a323c",
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10),
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        self.tb_var = tk.BooleanVar(value=bool(self.app.cfg.get("transparent_bg", True)))
        cb = tk.Checkbutton(
            look, text="背景完全透明（仅 Windows 有效）", variable=self.tb_var,
            command=self._on_transparent_toggle, bg=BG_PANEL, fg=FG_SUB,
            selectcolor=ENTRY_BG, activebackground=BG_PANEL,
            activeforeground=FG_MAIN, font=(UI_FONT, 9),
            highlightthickness=0, bd=0,
        )
        cb.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        if not sys.platform.startswith("win"):
            cb.configure(state="disabled")

        # ---- 底部按钮 ----
        bottom = tk.Frame(self, bg=BG_PANEL)
        bottom.pack(fill="x", padx=12, pady=(12, 12))
        tk.Button(
            bottom, text="保存并关闭", command=self._save_and_close,
            bg="#2f6fb5", fg="#ffffff", activebackground="#3b82d1",
            activeforeground="#ffffff", relief="flat", bd=0,
            padx=14, pady=5, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right")
        tk.Button(
            bottom, text="取消", command=self._close,
            bg="#2a323c", fg=FG_MAIN, activebackground="#3a4550",
            activeforeground=FG_MAIN, relief="flat", bd=0,
            padx=14, pady=5, font=(UI_FONT, 10), cursor="hand2",
        ).pack(side="right", padx=(0, 8))

    def _place_near_main(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = self.app.root.winfo_x() - w - 24
        y = self.app.root.winfo_y()
        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 10))
        self.geometry(f"+{x}+{y}")

    # ---------------- 列表操作 ---------------- #
    def _refresh_list(self) -> None:
        self.listbox.delete(0, "end")
        t = today()
        for it in self.items:
            try:
                r = item_remaining(it, t)
            except Exception:
                r = None
            if r is None:
                left = "数据错误"
            elif r > 0:
                left = f"还有 {r} 天"
            elif r == 0:
                left = "就是今天"
            else:
                left = f"已过 {-r} 天"
            self.listbox.insert("end", f"{it['name']} ｜ {item_rule_text(it)} ｜ {left}")
        if self.editing_index is not None and 0 <= self.editing_index < len(self.items):
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(self.editing_index)

    def _on_select(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        if i >= len(self.items):
            return
        self.editing_index = i
        it = self.items[i]
        self.name_var.set(it["name"])
        self.mode_var.set(it["mode"])
        if it["mode"] == "date":
            d = date.fromisoformat(it["date"])
            self.date_var.set(f"{d.year}年{d.month:02d}月{d.day:02d}日")
        else:
            self.days_var.set(str(it["days"]))
        self.apply_btn.configure(text="更新选中项")
        self._update_mode_state()

    def _rename_from_list(self) -> None:
        """列表项双击 → 弹出重命名对话框，改完后同步到上方表单。"""
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        if i >= len(self.items):
            return
        item = self.items[i]
        new_name = RenameDialog(self, item.get("name", "")).result
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        item["name"] = new_name
        if self.editing_index == i:
            self.name_var.set(new_name)
        self._refresh_list()

    def _new_item(self) -> None:
        self.editing_index = None
        self.name_var.set("")
        self.mode_var.set("days")
        self.days_var.set("30")
        self.date_var.set((today() + timedelta(days=30)).strftime("%Y年%m月%d日"))
        self.apply_btn.configure(text="添加到列表")
        self.listbox.selection_clear(0, "end")
        self._update_mode_state()

    def _delete_item(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一项", parent=self)
            return
        i = sel[0]
        if not messagebox.askyesno("确认", f"确定删除「{self.items[i]['name']}」吗？", parent=self):
            return
        del self.items[i]
        self._new_item()
        self._refresh_list()

    def _move(self, delta: int) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if not (0 <= j < len(self.items)):
            return
        self.items[i], self.items[j] = self.items[j], self.items[i]
        self.editing_index = j
        self._refresh_list()

    def _update_mode_state(self) -> None:
        is_days = self.mode_var.get() == "days"
        self.days_entry.configure(state="normal" if is_days else "disabled")
        self.date_entry.configure(state="disabled" if is_days else "normal")

    # ---------------- 增改 ---------------- #
    def _apply_item(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请填写名称", parent=self)
            return

        t = today()
        if self.mode_var.get() == "days":
            try:
                n = int(self.days_var.get().strip())
            except ValueError:
                messagebox.showwarning("提示", "天数必须是整数", parent=self)
                return
            if not (1 <= n <= MAX_DAYS):
                messagebox.showwarning("提示", f"天数必须在 1 ~ {MAX_DAYS} 之间", parent=self)
                return
            # 基准日期写入今天；下次启动时会自动刷新为启动当天
            item = {"name": name, "mode": "days", "days": n, "base": t.isoformat()}
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
            item = {"name": name, "mode": "date", "date": d.isoformat()}

        if self.editing_index is None:
            self.items.append(item)
            self.editing_index = len(self.items) - 1
        else:
            self.items[self.editing_index] = item
        self._refresh_list()

    # ---------------- 外观回调 ---------------- #
    def _on_alpha(self, _value=None) -> None:
        self.app.cfg["alpha"] = round(float(self.alpha_var.get()), 2)
        self.app.apply_style()

    def _on_transparent_toggle(self) -> None:
        self.app.cfg["transparent_bg"] = bool(self.tb_var.get())
        self.app.apply_style()

    # ---------------- 保存 / 关闭 ---------------- #
    def _save_and_close(self) -> None:
        try:
            font_size = int(self.font_var.get())
        except (tk.TclError, ValueError):
            font_size = 14
        font_size = max(8, min(48, font_size))

        self.app.cfg["items"] = [dict(it) for it in self.items]
        self.app.cfg["font_size"] = font_size
        self.app.cfg["alpha"] = round(float(self.alpha_var.get()), 2)
        self.app.cfg["transparent_bg"] = bool(self.tb_var.get())
        save_config(self.app.cfg)

        self.app.apply_style()
        self.app.rebuild_rows()
        self.app.refresh()
        self._close()

    def _close(self) -> None:
        self.app.settings = None
        self.destroy()


# --------------------------------------------------------------------------- #
def main() -> None:
    CountdownApp().run()


if __name__ == "__main__":
    main()