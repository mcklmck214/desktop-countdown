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
    return _bootstrap_dir() or home_dir()


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


def default_config():
    t = today().isoformat()
    return {
        "alpha": 0.72,
        "font_size": 25,
        "bg_mode": "panel",
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
    for k in ("alpha", "font_size", "bg_mode", "style_version", "locked", "topmost",
              "auto_start", "hidden", "x", "y", "text_color", "time_color",
              "menu_text_color", "timer_colors"):
        if k in data:
            cfg[k] = data[k]
    # 旧版存档只有 transparent_bg，未迁移时统一按新版默认（深色底板）显示
    if cfg.get("bg_mode") not in ("panel", "transparent"):
        cfg["bg_mode"] = "panel"
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
    return cfg


def save_config(cfg):
    path = get_config_path()
    tmp = path + ".tmp"
    try:
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
