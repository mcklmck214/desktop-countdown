#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无名小工具 · 多语言
从 lang.json 加载 zh / en / ja 三语文案。
"""

import json
import os
import sys

from utils import resource_dir


def get_resource_path(relative_path):
    """资源文件路径：兼容 PyInstaller 单文件打包后的临时目录。"""
    return os.path.join(resource_dir(), relative_path)


class LanguageManager:
    """多语言管理器：从 lang.json 加载 zh / en / ja 三语文案。"""

    SUPPORTED = ("zh", "en", "ja")
    _instance = None

    def __init__(self, lang="zh"):
        self._data = {}
        self._lang = lang if lang in self.SUPPORTED else "zh"
        self._load()

    @classmethod
    def instance(cls, lang=None):
        if cls._instance is None:
            cls._instance = cls(lang or "zh")
        elif lang is not None:
            cls._instance.set_language(lang)
        return cls._instance

    def _load(self):
        path = get_resource_path("lang.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception as exc:
            print(f"[LanguageManager] 加载 lang.json 失败: {exc}", file=sys.stderr)
            self._data = {}

    def set_language(self, lang):
        if lang in self.SUPPORTED:
            self._lang = lang

    @property
    def language(self):
        return self._lang

    def get(self, key, **kwargs):
        """取翻译文案，支持 {placeholder} 格式化；缺失时回退 zh，再回退 key。"""
        text = self._data.get(self._lang, {}).get(key)
        if text is None:
            text = self._data.get("zh", {}).get(key)
        if text is None:
            text = key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text

    def get_list(self, key):
        """取列表型文案（如 guide_steps）。"""
        value = self._data.get(self._lang, {}).get(key)
        if value is None:
            value = self._data.get("zh", {}).get(key)
        if not isinstance(value, list):
            return []
        return value
