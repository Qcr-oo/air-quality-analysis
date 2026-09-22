# -*- coding: utf-8 -*-
"""
第 1 步：从 1.89 GB 原始数据里抽一个小样本。

【为什么要抽样？】
    原始数据 1233 万行 / 1.89 GB。如果一上来就用全量：
      - 每次调试都要等几分钟，改一行代码等一次，效率极低
      - 内存可能直接爆掉
      - 你还没搞清楚逻辑，就已经被性能问题劝退了
    先用 5 万行把「逻辑」跑通，最后再换全量 —— 这是标准做法。

【为什么这一步不用 pandas？】
    这一步只做「读一行、写一行」，不需要任何分析能力。
    用纯标准库 csv 逐行流式处理，内存占用恒定（几百 KB），
    不会把 1.89 GB 全部读进内存。
    —— 工具要选合适的，不是越高级越好。

运行：
    python step1_sample.py
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (RAW_COLUMNS, SAMPLE_PATH, SAMPLE_TARGET_PER_YEAR, YEARS,
                    raw_file)


def estimate_step(year, target):
    """
    估算「每隔多少行取一行」才能得到目标行数。

    为什么要估算？因为逐行数一遍文件有多少行，等于把文件读了一遍。
    用「文件大小 / 平均每行字节数」可以快速估出大概行数。
    """
    path = raw_file(year)
    if not os.path.isfile(path):
        return None, None
    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        # 读前 200 行算平均行长
        n = 0
        total = 0
        for line in fh:
            total += len(line.encode("utf-8"))
            n += 1
            if n >= 200:
                break
    if n == 0:
        return None, None
    avg = total / n
    est_rows = int(size / avg)
    step = max(1, est_rows // target)
    return est_rows, step


def pick_row(row):
    """
    从原始 21 列里挑出需要的列，并做最基本的整理。

    注意：这里【不做】日期格式转换 —— 那是下一步（清洗）的事。
    本步只负责「把数据搬过来」，保持职责单一。
    """
    if len(row) < 21:
        return None
    out = []
    for v in row:
        v = (v or "").strip()
        out.append(v)
    return out


def main():
    t0 = time.time()
    print("=" * 68)
    print(" 第 1 步：抽样 —— 从原始数据抽取小样本")
    print("=" * 68)
    print("目标：每年约 %s 行\n" % format(SAMPLE_TARGET_PER_YEAR, ","))

    # 先把每年的抽样间隔算出来
    plan = []
    for y in YEARS:
        est, step = estimate_step(y, SAMPLE_TARGET_PER_YEAR)
        if est is None:
            print("  %d 年：原始文件缺失，跳过" % y)
            continue
        plan.append((y, step))
        print("  %d 年：估计 %s 行 → 每隔 %d 行取 1 行"
              % (y, format(est, ","), step))
    print()

    total_written = 0
    with open(SAMPLE_PATH, "w", encoding="utf-8", newline="") as out_fh:
        writer = csv.writer(out_fh)
        writer.writerow(RAW_COLUMNS)

        for y, step in plan:
            written = 0
            with open(raw_file(y), "r", encoding="utf-8",
                      errors="replace", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)                      # 跳过表头
                for i, row in enumerate(reader):
                    if i % step:                        # 不是采样点，跳过
                        continue
                    r = pick_row(row)
                    if r is None:
                        continue
                    writer.writerow(r)
                    written += 1
            total_written += written
            print("  %d 年：写入 %s 行" % (y, format(written, ",")))

    size_mb = os.path.getsize(SAMPLE_PATH) / 1024 / 1024
    print()
    print("=" * 68)
    print(" 完成！用时 %.1f 秒" % (time.time() - t0))
    print(" 样本文件：%s" % SAMPLE_PATH)
    print(" 总行数：%s" % format(total_written, ","))
    print(" 文件大小：%.1f MB" % size_mb)
    print("=" * 68)
    print()
    print("下一步：python step2_explore.py   （看看这份数据长什么样）")


if __name__ == "__main__":
    main()
