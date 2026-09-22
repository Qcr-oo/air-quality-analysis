# -*- coding: utf-8 -*-
"""
公共工具：控制台编码处理 + 报告输出。

【为什么需要这个模块】
    1. Windows 中文控制台默认编码是 GBK，输出 Unicode 特殊符号（✓ ⚠ 等）
       会直接抛 UnicodeEncodeError 让脚本崩溃。
    2. 每个脚本都复制一遍「同时输出到屏幕和文件」的代码，是重复劳动。

【解决方案】
    - enable_utf8()：把 stdout/stderr 切成 UTF-8，并且遇到无法编码的字符
      用 "?" 代替而不是崩溃。
    - Reporter：一行代码搞定「屏幕 + 文件」双写。
    - 约定：控制台输出只用 ASCII 标记（[OK] [X] [!] ->），
      花哨符号只用在写入文件的报告里。
"""
import sys


def enable_utf8():
    """
    把标准输出切换到 UTF-8 且不因编码失败而崩溃。

    注意 errors="replace"：遇到控制台不支持的字符就写 "?"，
    而不是抛异常。宁可显示得难看一点，也不能让脚本挂掉。
    """
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream, None)
        if s is not None and hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


class Reporter:
    """
    同时把内容写到「屏幕」和「报告文件」。

    用法：
        r = Reporter(out_path("report_xxx.txt"))
        r.title("第 3 步：数据清洗")
        r("  普通输出")
        r.close()
    """

    def __init__(self, report_path=None):
        enable_utf8()
        self.fh = None
        if report_path:
            self.fh = open(report_path, "w", encoding="utf-8")

    def __call__(self, text=""):
        """打印一行（同时进文件和屏幕）"""
        print(text)
        if self.fh:
            self.fh.write(str(text) + "\n")

    def title(self, text, width=70):
        """打印分节标题"""
        self("")
        self("=" * width)
        self(" " + text)
        self("=" * width)

    def raw(self, text):
        """只写文件，不打印（用于放不适合刷屏的长内容）"""
        if self.fh:
            self.fh.write(str(text) + "\n")

    def flush(self):
        if self.fh:
            self.fh.flush()

    def close(self):
        if self.fh:
            self.fh.close()
            self.fh = None


def human(n):
    """数字千分位，如 1234567 -> '1,234,567'"""
    return format(int(n), ",")
