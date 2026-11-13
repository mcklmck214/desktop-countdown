#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具 · 配置存储（Beta 0.4）
存档路径解析（含便携模式）、配置读写。
"""

import json
import os
import shutil
import sys

from utils import app_dir, home_dir, today

PORTABLE_FLAG = "portable.txt"
CONFIG_NAME = ".desktop_countdown.json"


def appdata_dir():
    """应用数据目录：Windows 为 %APPDATA%\\wmxgj，Linux 为 ~/.local/share/wmxgj。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or home_dir()
    elif sys.platform == "darwin":
        base = os.path.join(home_dir(), "Library", "Application Support")
    else:
        base = (os.environ.get("XDG_DATA_HOME")
                or os.path.join(home_dir(), ".local", "share"))
    return os.path.join(base, "wmxgj")


def _bootstrap_path():
    return os.path.join(home_dir(), ".desktop_countdown_dir.json")


def _flag_path():
    return os.path.join(app_dir(), PORTABLE_FLAG)


def is_portable():
    """程序目录下存在 portable.txt 即视为便携模式。"""
    return os.path.exists(_flag_path())


def _bootstrap_dir():
    """读取上次自定义的存档目录，无效则返回 None。"""
    bp = _bootstrap_path()
    if not os.path.exists(bp):
        return None
    try:
        with open(bp, "r", encoding="utf-8") as f:
            d = json.load(f).get("save_dir")
    except Exception:
        return None
    if d and os.path.isdir(d):
        return d
    return None


def get_save_dir():
    if is_portable():
        return app_dir()
    return _bootstrap_dir() or appdata_dir()


def get_config_path():
    return os.path.join(get_save_dir(), CONFIG_NAME)


def set_save_dir(new_dir):
    old_path = get_config_path()
    new_path = os.path.join(new_dir, CONFIG_NAME)
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


def set_portable(enable):
    """开启/关闭便携模式，并把现有存档迁移到新的存档目录。"""
    old_dir = get_save_dir()
    flag = _flag_path()
    if enable:
        with open(flag, "w", encoding="utf-8") as f:
            f.write("portable\n")
        new_dir = app_dir()
    else:
        try:
            os.remove(flag)
        except FileNotFoundError:
            pass
        new_dir = _bootstrap_dir() or home_dir()

    if os.path.abspath(old_dir) != os.path.abspath(new_dir):
        src = os.path.join(old_dir, CONFIG_NAME)
        dst = os.path.join(new_dir, CONFIG_NAME)
        try:
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
        except OSError:
            pass
    return new_dir


def migrate_legacy_config():
    """旧版本（Beta 0.4 及以前）把存档放在用户主目录；
    首次运行新版时把它复制到当前存档位置（保留原文件作备份）。"""
    new_path = get_config_path()
    if os.path.exists(new_path):
        return
    old_path = os.path.join(home_dir(), CONFIG_NAME)
    if os.path.abspath(old_path) == os.path.abspath(new_path):
        return
    try:
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy2(old_path, new_path)
            print("已迁移旧存档:", old_path, "->", new_path)
    except OSError as exc:
        print("迁移旧存档失败:", exc, file=sys.stderr)


def get_log_dir(cfg=None):
    """日志目录：配置了 log_dir 用之，否则为存档目录下的 logs。"""
    if cfg and cfg.get("log_dir"):
        return cfg["log_dir"]
    return os.path.join(get_save_dir(), "logs")


def default_config():
    t = today().isoformat()
    return {
        "alpha": 0.72,
        "font_size": 25,
        "bg_mode": "panel",
        "win_style": "edge_plate",
        "edge_color": None,
        "plate_color": None,
        "style_version": 2,
        "locked": False,
        "topmost": True,
        "auto_start": False,
        "hidden": False,
        "x": None,
        "y": None,
        "text_color": None,
        "time_color": None,
        "menu_text_color": None,
        "log_dir": None,
        "timer_colors": {},
        "items": [],
        "auto_hide": {"enabled": False, "apps": []},
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
    for k in ("alpha", "font_size", "bg_mode", "style_version", "locked", "topmost",
              "auto_start", "hidden", "x", "y", "text_color", "time_color",
              "menu_text_color", "log_dir", "win_style", "edge_color",
              "plate_color", "timer_colors"):
        if k in data:
            cfg[k] = data[k]
    # 旧版存档只有 transparent_bg，未迁移时统一按新版默认（深色底板）显示
    if cfg.get("bg_mode") not in ("panel", "transparent"):
        cfg["bg_mode"] = "panel"
    # 窗口类型（Beta 0.5）：旧档无此键时由 bg_mode 自动映射
    # panel（有边有底）→ edge_plate；transparent（无边无底）→ none
    if "win_style" not in data:
        cfg["win_style"] = ("none" if cfg.get("bg_mode") == "transparent"
                            else "edge_plate")
    if cfg.get("win_style") not in ("edge_plate", "edge_only", "none"):
        cfg["win_style"] = "edge_plate"
    # 仍然是旧默认透明度 0.90 的，跟新默认一起变薄（用户手动调过的不动）
    if "style_version" not in data:
        try:
            if float(cfg.get("alpha", 0.72)) == 0.9:
                cfg["alpha"] = 0.72
        except (TypeError, ValueError):
            cfg["alpha"] = 0.72
    if isinstance(data.get("items"), list):
        cfg["items"] = [
            it for it in data["items"]
            if isinstance(it, dict) and it.get("name") and it.get("mode") in ("days", "date")
        ]
    # Beta 0.6：自动隐藏名单
    ah = data.get("auto_hide")
    if isinstance(ah, dict):
        apps = ah.get("apps")
        if isinstance(apps, list):
            cfg["auto_hide"]["apps"] = [
                str(a).strip() for a in apps if isinstance(a, str) and a.strip()
            ]
        if isinstance(ah.get("enabled"), bool):
            cfg["auto_hide"]["enabled"] = ah["enabled"]
    return cfg


def save_config(cfg):
    path = get_config_path()
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        print("保存配置失败:", exc, file=sys.stderr)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
