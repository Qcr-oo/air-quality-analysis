# -*- coding: utf-8 -*-
"""
全局配置：所有路径和参数集中在这里。

【为什么要有这个文件】
    初学者最常见的坏习惯，是把路径写死在每个脚本里。
    一旦数据挪个位置，就要改十几个文件。
    集中配置之后，只需要改这里一处 —— 这是工程习惯，面试也可能被问。

用法：
    from config import RAW_DIR, WORK_DIR, OUT_DIR, YEARS
"""
import os

# ---------------- 路径 ----------------
# 目录层级（注意：本文件在 src/ 里，所以要往上退两层才到毕业设计根目录）
#   F:\myprogect\01-毕业设计\            <- PROJECT_DIR
#   F:\myprogect\01-毕业设计\07-系统实现\  <- BASE_DIR   （本项目根目录）
#   F:\myprogect\01-毕业设计\07-系统实现\src\  <- SRC_DIR （本文件所在目录）
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SRC_DIR)
PROJECT_DIR = os.path.dirname(BASE_DIR)

RAW_DIR = os.path.join(PROJECT_DIR, "05-数据集", "空气质量数据")   # 原始 CSV（只读！）
WORK_DIR = os.path.join(BASE_DIR, "data")        # 中间数据（清洗后的）
OUT_DIR = os.path.join(BASE_DIR, "output")       # 图表、结果表
DOC_DIR = os.path.join(BASE_DIR, "docs")         # 学习笔记

for _d in (WORK_DIR, OUT_DIR, DOC_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------- 数据参数 ----------------
YEARS = [2014, 2015, 2016, 2017, 2018]

# 原始 CSV 的列（21 列，顺序固定）
RAW_COLUMNS = [
    "release_date", "province_code", "province", "city_code", "city_label",
    "PM25", "PM25_24h", "PM10", "PM10_24h", "SO2", "NO2", "CO", "O3", "O3_8h",
    "AQI", "grade_level", "pollutions", "quality", "lat", "lon", "sandstorm",
]

# 污染物列（数值型）
POLLUTANT_COLS = ["PM25", "PM10", "SO2", "NO2", "CO", "O3", "O3_8h"]

# ⚠️ 陷阱 1：原始日期是「日/月/年」，不是「月/日/年」
DATE_FORMAT = "%d/%m/%Y %H:%M:%S"

# ⚠️ 陷阱 2：原始 CSV 里这两列的名字和内容是对调的
#   CSV 的 pollutions 列 → 实际存的是空气质量描述（优/良/…）
#   CSV 的 quality   列 → 实际存的是首要污染物（PM25/PM10/…）
# 下面定义清洗后正确的列名，避免以后混淆
COL_QUALITY_DESC = "quality_desc"      # 空气质量描述：优 / 良 / 轻度污染 …
COL_MAIN_POLLUTANT = "main_pollutant"  # 首要污染物：PM25 / PM10 / O3 / PM25,PM10 …

# 空气质量等级码表（AQI 区间 → 等级）
AQI_GRADE = [
    (0, 50, 1, "优"),
    (51, 100, 2, "良"),
    (101, 150, 3, "轻度污染"),
    (151, 200, 4, "中度污染"),
    (201, 300, 5, "重度污染"),
    (301, 9999, 6, "严重污染"),
]

# ---------------- 抽样参数（先小后大）----------------
# 第一阶段只用小样本把逻辑跑通，避免一上来就啃 1.89 GB
SAMPLE_TARGET_PER_YEAR = 10000     # 每年抽约 1 万行
SAMPLE_PATH = os.path.join(WORK_DIR, "sample.csv")


def raw_file(year):
    """返回某年的原始 CSV 路径"""
    return os.path.join(RAW_DIR, "%d_air_city_hour.csv" % year)


def out_path(name):
    """输出文件路径（放 output/ 下）"""
    return os.path.join(OUT_DIR, name)


def work_path(name):
    """中间数据路径（放 data/ 下）"""
    return os.path.join(WORK_DIR, name)


if __name__ == "__main__":
    print("BASE_DIR   =", BASE_DIR)
    print("RAW_DIR    =", RAW_DIR, "(存在)" if os.path.isdir(RAW_DIR) else "(不存在!)")
    print("WORK_DIR   =", WORK_DIR)
    print("OUT_DIR    =", OUT_DIR)
    print("原始文件：")
    for y in YEARS:
        p = raw_file(y)
        ok = os.path.isfile(p)
        size = "%.1f MB" % (os.path.getsize(p) / 1024 / 1024) if ok else "-"
        print("   %d  %-8s %s" % (y, size, p if ok else "缺失"))
