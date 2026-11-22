#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具 · 弹窗集合
条目编辑、新增倒计时、选色、默认/文字设置、引导、关于、工具箱等全部 Toplevel。

注意：主窗口为 overrideredirect(True) 无边框窗口，
弹窗一律不要调用 transient()，也不要把会弹出 Toplevel 的操作放进 tk.Menu。
"""

import os
import sys
import subprocess
import webbrowser
from datetime import date, timedelta

import tkinter as tk
from tkinter import messagebox, filedialog

from utils import (
    app_dir, resource_dir, today, parse_date_str, set_auto_start,
)
from storage import (
    save_config, get_save_dir, set_save_dir, is_portable, set_portable,
    default_config,
)
from config import (
    UI_FONT, MAX_DAYS, APP_VERSION, AUTHOR_NAME,
    BG_DARK, BG_PANEL, FG_MAIN, FG_SUB, ACCENT, ENTRY_BG, LINK_COLOR,
    GLASS_EDGE, BTN_BG, DEFAULT_COLORS, RANGE_KEYS,
    BILI_URL, AFDIAN_URL, QQ_FEEDBACK, QQ_CHAT, GITHUB_URL,
    make_button, center_window,
)


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

        self.title(self.app.lang("name_item"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(body, text=self.app.lang("name"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        self.name_var = tk.StringVar(value=item.get("name", ""))
        tk.Entry(body, textvariable=self.name_var, bg=ENTRY_BG, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat",
                 font=(UI_FONT, 11)).pack(fill="x", pady=(4, 10))

        tk.Label(body, text=self.app.lang("color"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")

        self.color_choice = tk.StringVar(
            value="custom" if item.get("name_color") else "default")
        cf = tk.Frame(body, bg=BG_PANEL)
        cf.pack(fill="x", pady=(4, 6))
        for text, val in ((self.app.lang("default"), "default"),
                          (self.app.lang("custom"), "custom")):
            tk.Radiobutton(
                cf, text=text, value=val, variable=self.color_choice,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        make_button(body, self.app.lang("pick_color_btn"), self._pick_color).pack(anchor="w", pady=(2, 12))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(4, 0))
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
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
            messagebox.showwarning(self.app.lang("prompt"), self.app.lang("name_empty"), parent=self)
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

        self.title(self.app.lang("time_item"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text=self.app.lang("item_label") + "：" + item.get('name', ''),
                 bg=BG_PANEL, fg=FG_SUB, font=(UI_FONT, 9),
                 anchor="w").grid(row=0, column=0, columnspan=3,
                                  sticky="w", pady=(0, 8))

        tk.Label(body, text=self.app.lang("mode"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value=item.get("mode", "days"))
        mf = tk.Frame(body, bg=BG_PANEL)
        mf.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0))
        for text, val in ((self.app.lang("days_countdown"), "days"),
                          (self.app.lang("date_countdown"), "date")):
            tk.Radiobutton(
                mf, text=text, value=val, variable=self.mode_var,
                command=self._update_state,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        tk.Label(body, text=self.app.lang("days"), bg=BG_PANEL, fg=FG_MAIN,
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

        tk.Label(body, text=self.app.lang("date"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=3, column=0, sticky="w", pady=4)
        init_date_text = ""
        if item.get("mode") == "date":
            try:
                d = date.fromisoformat(item["date"])
                init_date_text = f"{d.year}/{d.month:02d}/{d.day:02d}"
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

        tk.Label(body, text=self.app.lang("color"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=4, column=0, sticky="w", pady=(10, 4))
        self.color_choice = tk.StringVar(
            value="custom" if item.get("timer_color") else "default")
        cf = tk.Frame(body, bg=BG_PANEL)
        cf.grid(row=4, column=1, columnspan=2, sticky="w",
                padx=(8, 0), pady=(10, 4))
        for text, val in ((self.app.lang("default"), "default"),
                          (self.app.lang("custom"), "custom")):
            tk.Radiobutton(
                cf, text=text, value=val, variable=self.color_choice,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))
        make_button(body, self.app.lang("pick_color_btn"), self._pick_color).grid(
            row=5, column=1, sticky="w", padx=(8, 0), pady=(0, 10))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        make_button(btns, self.app.lang("delete"), self._delete).pack(side="left")
        self.reset_btn = make_button(btns, self.app.lang("reset_base_today"),
                                     self._reset_base)
        self.reset_btn.pack(side="left", padx=(8, 0))
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_state()
        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window(self)

    def _update_state(self):
        if self.mode_var.get() == "days":
            self.days_entry.configure(state="normal")
            self.date_entry.configure(state="disabled")
            self.reset_btn.configure(state="normal")
        else:
            self.days_entry.configure(state="disabled")
            self.date_entry.configure(state="normal")
            self.reset_btn.configure(state="disabled")

    def _pick_color(self):
        dlg = PickColorDialog(
            self, self.app,
            initial_color=self.custom_color or ACCENT,
            with_alpha=False,
        )
        if dlg.result:
            self.custom_color = dlg.result[0]
            self.color_choice.set("custom")

    def _reset_base(self):
        """把该条目的基准日重置为今天（连续打卡 / 重新计时用）。"""
        # 如果用户同时也修改了输入框里的天数，一并应用
        if self.mode_var.get() == "days":
            try:
                n = int(self.days_var.get().strip())
                if not (0 <= n <= MAX_DAYS):
                    raise ValueError
            except ValueError:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("days_not_int"), parent=self)
                return
            self.item["days"] = n

        self.item["base"] = today().isoformat()
        save_config(self.app.cfg)

        # 关键：必须调用 rebuild_rows 才能重新排序并强制刷新界面
        self.app.rebuild_rows()
        self.app.refresh()

        messagebox.showinfo(self.app.lang("prompt"),
                            self.app.lang("base_reset_done"), parent=self)
        # 重置成功后直接关闭弹窗，让用户看到主界面的变化
        self.destroy()

    def _ok(self):
        mode = self.mode_var.get()
        if mode == "days":
            try:
                n = int(self.days_var.get().strip())
            except ValueError:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("days_not_int"), parent=self)
                return
            if not (0 <= n <= MAX_DAYS):
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("days_out_of_range", max=MAX_DAYS), parent=self)
                return
            data = {"mode": "days", "days": n}
        else:
            try:
                d = parse_date_str(self.date_var.get())
            except ValueError as exc:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang(str(exc)), parent=self)
                return
            delta = (d - today()).days
            if delta < 0:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("date_before_today"), parent=self)
                return
            if delta > MAX_DAYS:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("date_too_far", max=MAX_DAYS), parent=self)
                return
            data = {"mode": "date", "date": d.isoformat()}
        data["timer_color"] = (self.custom_color
                               if self.color_choice.get() == "custom" else None)
        self.result = data
        self.destroy()

    def _delete(self):
        name = self.item.get("name", "")
        if not messagebox.askyesno(self.app.lang("delete_title"),
                                   self.app.lang("delete_confirm", name=name),
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

        self.title(self.app.lang("add_countdown"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text=self.app.lang("name"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar(value="")
        tk.Entry(body, textvariable=self.name_var, bg=ENTRY_BG, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat",
                 font=(UI_FONT, 10)).grid(row=0, column=1, columnspan=2,
                                          sticky="ew", pady=4, padx=(8, 0))

        tk.Label(body, text=self.app.lang("method"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="days")
        mf = tk.Frame(body, bg=BG_PANEL)
        mf.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0))
        for text, val in ((self.app.lang("n_days"), "days"),
                          (self.app.lang("target_date"), "date")):
            tk.Radiobutton(
                mf, text=text, value=val, variable=self.mode_var,
                command=self._update_state,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        tk.Label(body, text=self.app.lang("days"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        self.days_var = tk.StringVar(value="30")
        self.days_entry = tk.Entry(body, textvariable=self.days_var,
                                   bg=ENTRY_BG, fg=FG_MAIN,
                                   disabledbackground="#171c22",
                                   disabledforeground="#5a6773",
                                   insertbackground=FG_MAIN,
                                   relief="flat", font=(UI_FONT, 10), width=8)
        self.days_entry.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        tk.Label(body, text=self.app.lang("date"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=3, column=0, sticky="w", pady=4)
        self.date_var = tk.StringVar(value=(today() + timedelta(days=30)).strftime("%Y/%m/%d"))
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
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_state()
        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
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
            messagebox.showwarning(self.app.lang("prompt"), self.app.lang("name_empty"), parent=self)
            return
        t = today()
        if self.mode_var.get() == "days":
            try:
                n = int(self.days_var.get().strip())
            except ValueError:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("days_not_int"), parent=self)
                return
            if not (0 <= n <= MAX_DAYS):
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("days_out_of_range", max=MAX_DAYS), parent=self)
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
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang(str(exc)), parent=self)
                return
            delta = (d - t).days
            if delta < 0:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("date_before_today"), parent=self)
                return
            if delta > MAX_DAYS:
                messagebox.showwarning(self.app.lang("prompt"), self.app.lang("date_too_far", max=MAX_DAYS), parent=self)
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
        ("color_black", "#000000"), ("color_white", "#FFFFFF"), ("color_red", "#EF5350"),
        ("color_orange", "#FF9800"), ("color_yellow", "#FFCA28"), ("color_green", "#66BB6A"),
        ("color_cyan", "#26C6DA"), ("color_blue", "#42A5F5"), ("color_purple", "#AB47BC"),
        ("color_pink", "#F06292"), ("color_gray", "#90A4AE"),
    ]

    def __init__(self, parent, app, initial_color="#ffffff", initial_alpha=0.9,
                 with_alpha=True):
        super().__init__(parent)
        self.app = app
        self.result = None
        self.current_color = self._norm(initial_color)

        self.title(self.app.lang("pick_color"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # 预设颜色
        tk.Label(body, text=self.app.lang("preset_colors"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        pg = tk.Frame(body, bg=BG_PANEL)
        pg.pack(fill="x", pady=(4, 8))
        for i, (key, hexv) in enumerate(self.PRESETS):
            label = self.app.lang(key)
            b = tk.Button(pg, text=label, bg=hexv,
                          fg="#000000" if key in ("color_white", "color_yellow") else "#ffffff",
                          activebackground=hexv, relief="flat", bd=0,
                          font=(UI_FONT, 9), width=4, cursor="hand2")
            b.configure(command=lambda c=hexv: self._set_color(c))
            b.grid(row=i // 6, column=i % 6, padx=2, pady=2, sticky="ew")
        for c in range(6):
            pg.columnconfigure(c, weight=1)

        # RGB
        tk.Label(body, text=self.app.lang("rgb_color"), bg=BG_PANEL, fg=FG_MAIN,
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
        make_button(rgb_row, self.app.lang("change"), self._apply_rgb).pack(side="left")

        # 透明度（仅全局设置时显示）
        self.alpha_var = tk.DoubleVar(
            value=max(0.15, min(1.0, float(initial_alpha))))
        if with_alpha:
            tk.Label(body, text=self.app.lang("alpha"), bg=BG_PANEL, fg=FG_MAIN,
                     font=(UI_FONT, 10), anchor="w").pack(fill="x", pady=(8, 0))
            tk.Scale(
                body, from_=0.15, to=1.0, resolution=0.05, orient="horizontal",
                variable=self.alpha_var, bg=BG_PANEL, fg=FG_MAIN,
                troughcolor=ENTRY_BG, highlightthickness=0, bd=0,
                length=260, font=(UI_FONT, 9),
            ).pack(fill="x", pady=(2, 8))

        # 预览
        tk.Label(body, text=self.app.lang("preview"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), anchor="w").pack(fill="x")
        self.preview = tk.Label(body, text="", bg=self.current_color,
                                height=2, relief="solid", bd=1)
        self.preview.pack(fill="x", pady=(4, 10))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x")
        make_button(btns, self.app.lang("confirm"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
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

        self.title(self.app.lang("timer_colors"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(2, weight=1)

        for i, key in enumerate(RANGE_KEYS):
            label = self.app.lang(key)
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
                rf, text=self.app.lang("default"),
                value="default", variable=var,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 8))
            swatch = tk.Label(rf, text="   ", bg=default_color, width=3,
                              relief="solid", bd=1)
            swatch.pack(side="left", padx=(0, 12))

            tk.Radiobutton(
                rf, text=self.app.lang("custom"), value="custom", variable=var,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 8))
            make_button(rf, self.app.lang("pick"),
                        lambda k=key: self._pick(k)).pack(side="left")

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=len(RANGE_KEYS), column=0, columnspan=3,
                  sticky="ew", pady=(10, 0))
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
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

        self.title(self.app.lang("default_settings"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        # 文字大小
        tk.Label(body, text=self.app.lang("font_size"), bg=BG_PANEL, fg=FG_MAIN,
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
        self._color_row(body, 1, self.app.lang("text_color"), self.text_choice,
                        lambda: self.text_color,
                        lambda c: setattr(self, "text_color", c))

        # 计时器颜色
        tk.Label(body, text=self.app.lang("timer_colors"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=2, column=0, sticky="w", pady=4)
        make_button(body, self.app.lang("change"), self._open_timer_colors).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # 时间颜色
        self.time_choice = tk.StringVar(
            value="custom" if app.cfg.get("time_color") else "default")
        self.time_color = app.cfg.get("time_color")
        self._color_row(body, 3, self.app.lang("time_color"), self.time_choice,
                        lambda: self.time_color,
                        lambda c: setattr(self, "time_color", c))

        # 菜单文字颜色
        self.menu_choice = tk.StringVar(
            value="custom" if app.cfg.get("menu_text_color") else "default")
        self.menu_color = app.cfg.get("menu_text_color")
        self._color_row(body, 4, self.app.lang("menu_text_color"), self.menu_choice,
                        lambda: self.menu_color,
                        lambda c: setattr(self, "menu_color", c))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window(self)

    def _color_row(self, body, row, label, choice_var, getter, setter):
        tk.Label(body, text=label, bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=row, column=0, sticky="w", pady=4)
        rf = tk.Frame(body, bg=BG_PANEL)
        rf.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        tk.Radiobutton(
            rf, text=self.app.lang("default"), value="default", variable=choice_var,
            bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
            activebackground=BG_PANEL, activeforeground=FG_MAIN,
            font=(UI_FONT, 10), bd=0, highlightthickness=0,
        ).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            rf, text=self.app.lang("custom"), value="custom", variable=choice_var,
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

        make_button(rf, self.app.lang("pick_color_btn"), pick).pack(side="left")

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

        self.title(self.app.lang("text_settings"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text=self.app.lang("font_size"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.font_var = tk.IntVar(
            value=max(8, min(48, int(app.cfg.get("font_size", 25)))))
        tk.Spinbox(
            body, from_=8, to=48, textvariable=self.font_var, width=5,
            bg=ENTRY_BG, fg=FG_MAIN, buttonbackground=BTN_BG,
            insertbackground=FG_MAIN, relief="flat", font=(UI_FONT, 10),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        make_button(body, self.app.lang("default_settings"), self._open_default).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        make_button(btns, self.app.lang("done"), self._ok, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        center_window(self, parent)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
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

class GuideWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.index = 0

        self.title(self.app.lang("guide"))
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
        self.next_btn = make_button(btns, self.app.lang("next"), self._next, primary=True)
        self.next_btn.pack(side="right")
        self.prev_btn = make_button(btns, self.app.lang("prev"), self._prev)
        self.prev_btn.pack(side="right", padx=(0, 8))
        make_button(btns, self.app.lang("skip"), self._close).pack(side="left")

        self._render()
        center_window(self, parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _steps(self):
        return self.app._lang_mgr.get_list("guide_steps")

    def _render(self):
        steps = self._steps()
        title, lines = steps[self.index]
        self.step_label.configure(
            text=self.app.lang("step_counter", index=self.index + 1, total=len(steps)))

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", title + "\n", "h")
        for line in lines:
            self.text.insert("end", line + "\n", "b")
        self.text.configure(state="disabled")

        self.prev_btn.configure(state="normal" if self.index > 0 else "disabled")
        self.next_btn.configure(
            text=self.app.lang("start_using") if self.index == len(steps) - 1 else self.app.lang("next"))

    def _next(self):
        steps = self._steps()
        if self.index >= len(steps) - 1:
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

        self.title(self.app.lang("about"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=(14, 6))

        self.text = tk.Text(
            body, width=72, height=28, wrap="word",
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
        make_button(bottom, self.app.lang("close"), self.destroy, primary=True).pack(side="right")
        make_button(bottom, self.app.lang("export_log"), self._export_log).pack(
            side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        center_window(self, parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _export_log(self):
        self.app.export_log(parent=self)

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

        add("end", self.app.lang("app_title") + "\n", "title")
        add("end", f"{APP_VERSION}\n", "ver")

        add("end", self.app.lang("changelog") + "\n", "h")
        for line in self.app._lang_mgr.get_list("changelog_lines"):
            add("end", line + "\n", "b")

        add("end", self.app.lang("author") + "：", "h")
        self._insert_link(AUTHOR_NAME, "open", BILI_URL)
        add("end", "\n", "b")
        add("end", self.app.lang("author_desc") + "\n", "s")
        add("end", self.app.lang("ai_note") + "\n", "s")

        add("end", self.app.lang("support") + "\n", "h")
        add("end", self.app.lang("afdian") + "：", "b")
        self._insert_link("https://ifdian.net/a/wmxgj", "open", AFDIAN_URL)
        add("end", "\n", "b")

        add("end", self.app.lang("feedback") + "\n", "h")
        for label_key, (number, url, name) in (
            ("feedback_group", QQ_FEEDBACK),
            ("chat_group", QQ_CHAT),
        ):
            add("end", self.app.lang(label_key) + "：", "b")
            self._insert_link(number, "copy", number)
            add("end", "　", "b")
            self._insert_link(self.app.lang("join_group", name=name), "open", url)
            add("end", "\n", "b")

        add("end", self.app.lang("source") + "\n", "h")
        add("end", self.app.lang("github") + "：", "b")
        self._insert_link(GITHUB_URL, "open", GITHUB_URL)
        add("end", "\n", "b")

    def _on_link(self, mode, payload):
        if mode == "copy":
            try:
                self.clipboard_clear()
                self.clipboard_append(payload)
                self.update_idletasks()
                self.status.configure(text=self.app.lang("copied", payload=payload))
            except tk.TclError:
                self.status.configure(text=self.app.lang("copy_failed"))
        else:
            try:
                webbrowser.open(payload)
                self.status.configure(text=self.app.lang("browser_opened"))
            except Exception:
                msg = self.app.lang("browser_failed", payload=payload)
                self.status.configure(text=msg)
                messagebox.showwarning(self.app.lang("prompt"), msg, parent=self)
        try:
            self.after(2500, lambda: self.status.configure(text=""))
        except tk.TclError:
            pass


# --------------------------------------------------------------------------- #
# 工具箱
# --------------------------------------------------------------------------- #
class ToolboxWindow(tk.Toplevel):
    TOOLS = (
        ("download_tool", "Plain Craft Launcher 2.exe"),
        ("uninstall_tool", "geek.exe"),
    )

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.title(self.app.lang("toolbox"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        for key, exe in self.TOOLS:
            make_button(body, self.app.lang(key),
                        lambda e=exe: self._launch(e)).pack(fill="x", pady=3)

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(10, 0))
        make_button(btns, self.app.lang("close"), self.destroy, primary=True).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        center_window(self, parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _find_tool(self, exe):
        """工具位置：优先 exe 所在目录（单文件打包时才是真正的“程序目录”），
        其次 _MEIPASS（打包时随程序打入的副本）。"""
        for here in (app_dir(), resource_dir()):
            path = os.path.join(here, exe)
            if os.path.exists(path):
                return path
        return None

    def _launch(self, exe):
        path = self._find_tool(exe)
        if path is None:
            messagebox.showwarning(
                self.app.lang("toolbox"),
                self.app.lang("tool_not_found", exe=exe),
                parent=self)
            return
        here = os.path.dirname(path)
        try:
            subprocess.Popen([path], cwd=here)
        except OSError as exc:
            # 740 = ERROR_ELEVATION_REQUIRED，geek 等工具需要管理员权限
            if sys.platform.startswith("win") and getattr(exc, "winerror", None) == 740:
                self._launch_elevated(path, here)
            else:
                messagebox.showwarning(self.app.lang("toolbox"),
                                       self.app.lang("launch_failed", exc=exc), parent=self)

    def _launch_elevated(self, path, workdir):
        try:
            import ctypes
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", path, None, workdir, 1)
        except Exception as exc:
            messagebox.showwarning(self.app.lang("toolbox"),
                                   self.app.lang("elevate_failed", exc=exc), parent=self)
            return
        if rc <= 32:
            if rc == 1223:
                messagebox.showinfo(self.app.lang("toolbox"), self.app.lang("elevate_cancelled"), parent=self)
            else:
                messagebox.showwarning(
                    self.app.lang("toolbox"),
                    self.app.lang("elevate_failed", exc=f"error code {rc}"), parent=self)


# --------------------------------------------------------------------------- #
# 自动隐藏设置窗口（Beta 0.6）
# --------------------------------------------------------------------------- #
class AutoHideSettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.ah = app.cfg.setdefault("auto_hide", {"enabled": False, "apps": []})

        self.title(self.app.lang("auto_hide"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build()
        center_window(self, app.root)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self):
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # 启用开关
        row_en = tk.Frame(body, bg=BG_PANEL)
        row_en.pack(fill="x", pady=(0, 8))
        tk.Label(row_en, text=self.app.lang("enable_auto_hide"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=12, anchor="w").pack(side="left")
        self.enabled_var = tk.StringVar(
            value="on" if self.ah.get("enabled") else "off")
        for t, v in ((self.app.lang("off"), "off"), (self.app.lang("on"), "on")):
            tk.Radiobutton(
                row_en, text=t, value=v, variable=self.enabled_var,
                command=self._toggle_enabled,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        tk.Label(body, text=self.app.lang("hint_apps"),
                 bg=BG_PANEL, fg=FG_SUB, font=(UI_FONT, 9)).pack(anchor="w")

        # 名单列表
        list_frame = tk.Frame(body, bg=BG_PANEL)
        list_frame.pack(fill="both", expand=True, pady=6)
        self.listbox = tk.Listbox(
            list_frame, height=8, width=32,
            bg=ENTRY_BG, fg=FG_MAIN, selectbackground=ACCENT,
            selectforeground="#000000", font=(UI_FONT, 10),
            bd=0, highlightthickness=1, highlightcolor=ACCENT,
            highlightbackground=GLASS_EDGE, activestyle="none")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(list_frame, command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        self._refresh_list()

        # 添加 / 删除
        row_op = tk.Frame(body, bg=BG_PANEL)
        row_op.pack(fill="x", pady=(8, 4))
        self.entry = tk.Entry(
            row_op, bg=ENTRY_BG, fg=FG_MAIN, insertbackground=FG_MAIN,
            font=(UI_FONT, 10), bd=0, highlightthickness=1,
            highlightcolor=ACCENT, highlightbackground=GLASS_EDGE)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self._add_app())
        make_button(row_op, self.app.lang("add"), self._add_app).pack(side="left")

        row_del = tk.Frame(body, bg=BG_PANEL)
        row_del.pack(fill="x", pady=2)
        make_button(row_del, self.app.lang("remove_selected"), self._remove_app).pack(side="left")
        make_button(row_del, self.app.lang("clear"), self._clear_apps).pack(side="left", padx=(6, 0))

        # 提示
        tk.Label(body,
                 text=self.app.lang("process_hint"),
                 bg=BG_PANEL, fg=FG_SUB, font=(UI_FONT, 8),
                 justify="left").pack(anchor="w", pady=(6, 0))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(12, 0))
        make_button(btns, self.app.lang("done"), self._close, primary=True).pack(side="right")

        self.bind("<Escape>", lambda e: self._close())

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for name in self.ah.get("apps", []):
            self.listbox.insert(tk.END, name)

    def _toggle_enabled(self):
        self.ah["enabled"] = (self.enabled_var.get() == "on")
        save_config(self.app.cfg)

    def _add_app(self):
        name = self.entry.get().strip()
        if not name:
            return
        if name not in self.ah["apps"]:
            self.ah["apps"].append(name)
            save_config(self.app.cfg)
            self._refresh_list()
        self.entry.delete(0, tk.END)

    def _remove_app(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.listbox.get(sel[0])
        if name in self.ah["apps"]:
            self.ah["apps"].remove(name)
            save_config(self.app.cfg)
            self._refresh_list()

    def _clear_apps(self):
        if self.ah["apps"]:
            self.ah["apps"] = []
            save_config(self.app.cfg)
            self._refresh_list()

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# --------------------------------------------------------------------------- #
# 主设置窗口
# --------------------------------------------------------------------------- #
class SettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app

        self.title(self.app.lang("settings"))
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build()
        center_window(self, app.root)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self):
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        make_button(body, self.app.lang("add_countdown"), self._add_item).pack(fill="x", pady=3)

        # 最顶置
        row1 = tk.Frame(body, bg=BG_PANEL)
        row1.pack(fill="x", pady=3)
        tk.Label(row1, text=self.app.lang("topmost"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        self.topmost_var = tk.StringVar(
            value="on" if self.app.cfg.get("topmost", True) else "off")
        for t, v in ((self.app.lang("off"), "off"), (self.app.lang("on"), "on")):
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
        tk.Label(row2, text=self.app.lang("autostart"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        self.autostart_var = tk.StringVar(
            value="on" if self.app.cfg.get("auto_start", False) else "off")
        for t, v in ((self.app.lang("off"), "off"), (self.app.lang("on"), "on")):
            tk.Radiobutton(
                row2, text=t, value=v, variable=self.autostart_var,
                command=self._apply_autostart,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        # 便携模式
        row_p = tk.Frame(body, bg=BG_PANEL)
        row_p.pack(fill="x", pady=3)
        tk.Label(row_p, text=self.app.lang("portable"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        self.portable_var = tk.StringVar(value="on" if is_portable() else "off")
        for t, v in ((self.app.lang("off"), "off"), (self.app.lang("on"), "on")):
            tk.Radiobutton(
                row_p, text=t, value=v, variable=self.portable_var,
                command=self._apply_portable,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        # 语言（Beta 0.7）
        row_lang = tk.Frame(body, bg=BG_PANEL)
        row_lang.pack(fill="x", pady=3)
        tk.Label(row_lang, text=self.app.lang("language"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        self.lang_var = tk.StringVar(value=self.app.cfg.get("language", "zh"))
        for t, v in (("中文", "zh"), ("English", "en"), ("日本語", "ja")):
            tk.Radiobutton(
                row_lang, text=t, value=v, variable=self.lang_var,
                command=self._apply_language,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(8, 0))

        # 窗口类型（Beta 0.5）：即改即存、实时生效
        row_w = tk.Frame(body, bg=BG_PANEL)
        row_w.pack(fill="x", pady=3)
        tk.Label(row_w, text=self.app.lang("win_style"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        style_now = self.app.cfg.get("win_style")
        if style_now not in ("edge_plate", "edge_only", "none"):
            style_now = "edge_plate"
        self.win_style_var = tk.StringVar(value=style_now)
        for t, v in ((self.app.lang("style_edge_plate"), "edge_plate"),
                     (self.app.lang("style_edge_only"), "edge_only"),
                     (self.app.lang("style_none"), "none")):
            tk.Radiobutton(
                row_w, text=t, value=v, variable=self.win_style_var,
                command=self._apply_win_style,
                bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                activebackground=BG_PANEL, activeforeground=FG_MAIN,
                font=(UI_FONT, 10), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 2))

        # Linux 极简模式（Beta 0.8）：纯色底板 / 半透明
        if not sys.platform.startswith("win") and sys.platform != "darwin":
            row_linux = tk.Frame(body, bg=BG_PANEL)
            row_linux.pack(fill="x", pady=3)
            tk.Label(row_linux, text=self.app.lang("linux_simple"), bg=BG_PANEL,
                     fg=FG_MAIN, font=(UI_FONT, 10), width=15,
                     anchor="w").pack(side="left")
            self.linux_simple_var = tk.StringVar(
                value="solid" if self.app.cfg.get("linux_simple_plate") else "alpha")
            for t, v in ((self.app.lang("semi_transparent"), "alpha"),
                         (self.app.lang("solid"), "solid")):
                tk.Radiobutton(
                    row_linux, text=t, value=v, variable=self.linux_simple_var,
                    command=self._apply_linux_simple,
                    bg=BG_PANEL, fg=FG_MAIN, selectcolor=ENTRY_BG,
                    activebackground=BG_PANEL, activeforeground=FG_MAIN,
                    font=(UI_FONT, 10), bd=0, highlightthickness=0,
                ).pack(side="left", padx=(8, 0))

        # 边颜色 / 底板颜色（Beta 0.5）：选色即生效即保存
        self._add_color_row(body, self.app.lang("edge_color"), "edge_color", GLASS_EDGE)
        self._add_color_row(body, self.app.lang("plate_color"), "plate_color", BG_DARK)

        make_button(body, self.app.lang("text_settings"), self._open_text_settings).pack(
            fill="x", pady=3)
        make_button(body, self.app.lang("auto_hide_settings"), self._open_auto_hide).pack(
            fill="x", pady=3)

        # 存档位置
        row3 = tk.Frame(body, bg=BG_PANEL)
        row3.pack(fill="x", pady=3)
        tk.Label(row3, text=self.app.lang("save_dir"), bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        self.save_dir_label = tk.Label(
            row3, text=get_save_dir(), bg=BG_PANEL, fg=FG_SUB,
            font=(UI_FONT, 9), anchor="w")
        self.save_dir_label.pack(side="left", fill="x", expand=True, padx=(6, 6))
        make_button(row3, self.app.lang("choose_folder"), self._choose_save_dir).pack(side="right")

        make_button(body, self.app.lang("toolbox"), self._open_toolbox).pack(fill="x", pady=3)
        make_button(body, self.app.lang("about"), self._open_about).pack(fill="x", pady=3)
        make_button(body, self.app.lang("clear_all"), self._clear_all).pack(fill="x", pady=3)
        make_button(body, self.app.lang("close_app"), self._close_app).pack(fill="x", pady=3)

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.pack(fill="x", pady=(12, 0))
        make_button(btns, self.app.lang("done"), self._done, primary=True).pack(side="right")
        make_button(btns, self.app.lang("cancel"), self._cancel).pack(side="right", padx=(0, 8))

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

    def _apply_portable(self):
        on = self.portable_var.get() == "on"
        try:
            new_dir = set_portable(on)
        except OSError as exc:
            self.portable_var.set("on" if is_portable() else "off")
            messagebox.showwarning(self.app.lang("prompt"),
                                   self.app.lang("portable_switch_failed", exc=exc), parent=self)
            return
        save_config(self.app.cfg)
        try:
            self.save_dir_label.configure(text=new_dir)
        except tk.TclError:
            pass

    def _apply_language(self):
        lang = self.lang_var.get()
        if lang not in ("zh", "en", "ja"):
            return
        self.app.cfg["language"] = lang
        self.app._lang_mgr.set_language(lang)
        save_config(self.app.cfg)
        # 提示用户重启后全部生效；先实时更新窗口标题
        try:
            self.app.root.title(self.app.lang("app_title"))
        except tk.TclError:
            pass
        messagebox.showinfo(self.app.lang("prompt"),
                            self.app.lang("restart_hint"), parent=self)

    def _apply_win_style(self):
        self.app.cfg["win_style"] = self.win_style_var.get()
        save_config(self.app.cfg)
        self.app._apply_bg_and_alpha()
        self.app._apply_dwm_shadow()

    def _apply_linux_simple(self):
        self.app.cfg["linux_simple_plate"] = (self.linux_simple_var.get() == "solid")
        save_config(self.app.cfg)
        self.app._apply_bg_and_alpha()

    def _add_color_row(self, body, label, key, default):
        row = tk.Frame(body, bg=BG_PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_MAIN,
                 font=(UI_FONT, 10), width=15, anchor="w").pack(side="left")
        swatch = tk.Label(row, bg=self.app.cfg.get(key) or default, width=3,
                          relief="flat", bd=1, highlightthickness=1,
                          highlightbackground=FG_SUB)
        swatch.pack(side="left", padx=(0, 6))

        def pick():
            dlg = PickColorDialog(
                self, self.app,
                initial_color=self.app.cfg.get(key) or default,
                with_alpha=False,
            )
            if dlg.result:
                self.app.cfg[key] = dlg.result[0]
                save_config(self.app.cfg)
                swatch.configure(bg=self.app.cfg[key])
                self.app._apply_bg_and_alpha()

        def reset():
            self.app.cfg[key] = None
            save_config(self.app.cfg)
            swatch.configure(bg=default)
            self.app._apply_bg_and_alpha()

        make_button(row, self.app.lang("pick"), pick).pack(side="left", padx=(0, 4))
        make_button(row, self.app.lang("default"), reset).pack(side="left")

    def _open_text_settings(self):
        self.app.open_text_settings()
        try:
            self.lift()
        except tk.TclError:
            pass

    def _open_auto_hide(self):
        AutoHideSettingsWindow(self.app)
        try:
            self.lift()
        except tk.TclError:
            pass

    def _choose_save_dir(self):
        if is_portable():
            messagebox.showinfo(
                self.app.lang("prompt"), self.app.lang("portable_mode_on"),
                parent=self)
            return
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
        messagebox.showinfo(self.app.lang("prompt"),
                            self.app.lang("save_dir_changed", dir=d), parent=self)

    def _add_item(self):
        dlg = AddItemDialog(self, self.app)
        if dlg.result:
            self.app.cfg["items"].append(dlg.result)
            save_config(self.app.cfg)
            self.app.rebuild_rows()
            self.app.refresh()

    def _open_about(self):
        self.app.open_about()

    def _open_toolbox(self):
        self.app.open_toolbox()

    def _clear_all(self):
        if not messagebox.askyesno(
            self.app.lang("prompt"), self.app.lang("clear_confirm"), parent=self
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
        if messagebox.askyesno(self.app.lang("prompt"), self.app.lang("close_confirm"), parent=self):
            self.app.quit_app()

    def _done(self):
        save_config(self.app.cfg)
        self.destroy()

    def _cancel(self):
        self.destroy()

