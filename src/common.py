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
    让标准输出遇到无法编码的字符时不要崩溃。

    【重要修正 —— 这里踩过一个坑】
      最初的写法是 s.reconfigure(encoding="utf-8", errors="replace")，
      本意是解决 "⚠️ 等 emoji 导致 UnicodeEncodeError 让脚本崩溃" 的问题。

      但这会带来一个更严重的副作用：
        Windows 中文控制台的代码页是 GBK(936)，
        如果 Python 强行输出 UTF-8 字节，控制台会按 GBK 去解码，
        **中文全部变成乱码**（"北京" → "�������"）。

      【正确做法】保持控制台的原生编码，只把错误处理改成 replace：
        - 中文：用 GBK 输出 → 控制台按 GBK 解码 → 显示正常
        - emoji 等 GBK 打不出的字符：降级成 "?"，而不是抛异常中断脚本

      一句话：**只改"出错怎么办"，不要改"用什么编码"。**
    """
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream, None)
        if s is not None and hasattr(s, "reconfigure"):
            try:
                s.reconfigure(errors="replace")   # 保持编码不变，只改错误处理
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
        print(text, flush=True)
        if self.fh:
            self.fh.write(str(text) + "\n")
            # 立即刷盘：长时间运行的任务需要能从外部看到进度，
            # 否则文件缓冲会导致日志"看起来卡住了"。
            self.fh.flush()

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
