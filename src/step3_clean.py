# -*- coding: utf-8 -*-
"""
第 3 步：数据清洗与特征工程

【这一步做什么】
    把「能读的原始数据」变成「能分析的干净数据」。五件事：
      1. 修正日期格式（陷阱 1）
      2. 修正列名与内容对调（陷阱 2）
      3. 数值类型转换 + 缺失值处理（陷阱 4）
      4. 异常值识别
      5. 构造时间特征（年/月/日/小时/星期/季节/采暖季）

【清洗的铁律】
    每做一步修正，都要能「验证」。不能改完就说"好了"。
    本脚本最后用「月度 AQI 冬高夏低」这条物理规律反查日期改对了没有。

运行：
    python step3_clean.py
产出：
    data/clean_sample.csv        清洗后的数据
    output/report_clean.txt      清洗报告
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
from config import (COL_MAIN_POLLUTANT, COL_QUALITY_DESC, DATE_FORMAT,
                    POLLUTANT_COLS, SAMPLE_PATH, out_path, work_path)

# 各污染物的物理合理上限（μg/m³，CO 为 mg/m³）
# 依据：国标限值 + 极端污染事件的历史实测极值，再留一定余量
PHYSICAL_LIMITS = {
    "PM25": 1000,     # 国标日均限值 75；极端重污染可到 700-900
    "PM10": 2000,     # 国标日均限值 150；强沙尘暴可到 1500-2000
    "SO2": 1500,      # 国标日均限值 150
    "NO2": 500,       # 国标日均限值 80
    "CO": 20,         # 国标日均限值 4（mg/m³）
    "O3": 500,        # 国标 8h 限值 160
    "O3_8h": 500,
}


def season_of(month):
    """月份 -> 季节"""
    if month in (3, 4, 5):
        return "春季"
    if month in (6, 7, 8):
        return "夏季"
    if month in (9, 10, 11):
        return "秋季"
    return "冬季"          # 12, 1, 2


def main():
    r = Reporter(out_path("report_clean.txt"))

    r.title("第 3 步：数据清洗与特征工程")

    df = pd.read_csv(SAMPLE_PATH, dtype=str)
    n0 = len(df)
    r("")
    r("读入样本：%s 行 x %d 列" % (format(n0, ","), len(df.columns)))

    # ================================================================
    # 修正 1：日期格式（陷阱 1）
    # ================================================================
    r.title("修正 1：日期格式 —— 陷阱 1")

    r("""
  原始数据是「日/月/年」，不是「月/日/年」。

  如果按 %m/%d/%Y 解析：
    - 日 > 12 的行（约 61%）会直接解析失败
    - 日 <= 12 的行会被错误解析，日与月互换（7月1日 -> 1月7日）

  正确做法：明确指定 %d/%m/%Y，并用 errors='coerce' 把解析失败的
  变成 NaT（Not a Time）。这样能统计出失败了多少条，而不是静默出错。
""")

    raw_date = df["release_date"]
    dt = pd.to_datetime(raw_date, format=DATE_FORMAT, errors="coerce")
    n_fail = int(dt.isna().sum())

    r("  解析成功：%s 行" % format(n0 - n_fail, ","))
    r("  解析失败：%s 行  (%.2f%%)" % (format(n_fail, ","), n_fail / n0 * 100))
    if n_fail:
        r("  失败样例（前 3 条）：")
        for v in raw_date[dt.isna()].head(3):
            r("    %r" % v)

    df["datetime"] = dt
    df = df[df["datetime"].notna()].copy()
    r("")
    r("  -> 丢弃解析失败的行后，剩余 %s 行" % format(len(df), ","))

    r("""
  【交叉验证】如果「日/月/年」判断错了，会出现什么现象？
    正确解析后，每个月的记录数应该大致均匀（每月 28-31 天）。
    若日与月对调，1 月会变成 31 天、2 月变 29 天……而 13 月会解析失败。
    —— 这正是刚才 61% 失败的原因。
""")
    mc = df["datetime"].dt.month.value_counts().sort_index()
    r("  各月记录数：")
    r("    " + "  ".join("%d月:%-6s" % (m, format(c, ",")) for m, c in mc.items()))
    ratio = mc.max() / mc.min()
    r("    最多月 / 最少月 = %.2f  （接近 1 说明分布均匀，格式判断正确）" % ratio)

    # ================================================================
    # 修正 2：列名与内容对调（陷阱 2）
    # ================================================================
    r.title("修正 2：列名与内容对调 —— 陷阱 2")

    r("""
  原始 CSV 表头：... grade_level, pollutions, quality, lat, lon, sandstorm

  但实际内容是反的（EDA 已经用数据证明了）：
    CSV 的 pollutions 列 -> 「优 / 良 / 轻度污染 …」   这是【质量描述】
    CSV 的 quality   列 -> 「PM25 / PM10 / O3 …」    这是【首要污染物】

  铁证：pollutions 的各种取值行数，与 grade_level 的 1-6 完全一一对应。
""")
    r("  grade_level 与 pollutions 的对应关系：")
    cross = pd.crosstab(df["grade_level"], df["pollutions"])
    for g, row in cross.iterrows():
        items = [(c, int(v)) for c, v in row.items() if v > 0]
        r("    等级 %s -> %s" % (g, "  ".join("%s(%s)" % (c, format(v, ","))
                                              for c, v in items)))

    df[COL_QUALITY_DESC] = df["pollutions"].fillna("").str.strip()
    df[COL_MAIN_POLLUTANT] = df["quality"].fillna("").str.strip()
    df = df.drop(columns=["pollutions", "quality"])
    r("")
    r("  已重命名：pollutions -> %s ；quality -> %s"
      % (COL_QUALITY_DESC, COL_MAIN_POLLUTANT))

    r("""
  【逻辑闭环 —— 这段面试可以直接讲】
    quality 列的 NaN 数量         = 15,229
    pollutions 列「优」的数量      = 15,229
    两者完全相等。

    为什么？因为空气质量为「优」时，不存在首要污染物 —— 空气干净，
    没有哪个污染物超标。所以那一行的「首要污染物」字段自然是空的。
    这个等式把两列的关系彻底钉死了。
""")
    n_you = int((df[COL_QUALITY_DESC] == "优").sum())
    n_blank = int((df[COL_MAIN_POLLUTANT] == "").sum())
    r("    实测：%s='优' 的行 = %s ；%s 为空的行 = %s"
      % (COL_QUALITY_DESC, format(n_you, ","), COL_MAIN_POLLUTANT, format(n_blank, ",")))
    r("    是否相等：%s" % ("是 [OK]" if n_you == n_blank else "否 [X]"))

    # ================================================================
    # 修正 3：数值转换与缺失值
    # ================================================================
    r.title("修正 3：数值转换与缺失值 —— 陷阱 4")

    num_cols = POLLUTANT_COLS + ["AQI", "lat", "lon", "sandstorm"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    total = len(df)
    r("")
    r("  数值列缺失情况：")
    for c in num_cols:
        if c not in df.columns:
            continue
        n = int(df[c].isna().sum())
        pct = n / total * 100
        flag = "  <- 缺失严重！" if pct > 10 else ""
        r("    %-10s 缺失 %8s 行 (%.2f%%)%s" % (c, format(n, ","), pct, flag))

    r("""
  【为什么不能简单 dropna()？】
    o3_8h 缺失 31.5%。若直接 dropna()，会连带丢掉 1/3 的数据，
    而且丢掉的很可能不是随机的（某些城市/年份的设备就是不报 O3），
    这叫「非随机缺失」，直接删会造成偏差。

  【本项目的策略】
    - AQI 缺失 -> 丢弃该行（AQI 是核心分析指标，缺了没用）
    - 污染物缺失 -> 保留 NaN，分析时按需处理
      （pandas 的 mean() 会自动跳过 NaN，不影响结果）
""")
    before = len(df)
    df = df[df["AQI"].notna()].copy()
    r("  丢弃 AQI 缺失的行：%s 行 -> 剩余 %s 行"
      % (format(before - len(df), ","), format(len(df), ",")))

    # ================================================================
    # 修正 4：异常值识别
    # ================================================================
    r.title("修正 4：异常值识别")

    r("""
  EDA 的 describe() 显示有极端值：
    PM10 最大 8,577    PM25 最大 1,373    CO 最大 45.5

  8,577 的 PM10 是什么概念？强沙尘暴的实测极值也就 1,500-2,000。
  这基本可以断定是【数据错误】而不是真实污染事件。

  【处理策略：标记而不是删除】
    直接删掉是危险的 —— 万一是真事件（比如特大沙尘暴），删了就丢了信息。
    所以本脚本只【标记】哪些值超出物理上限，具体怎么处理留给分析阶段决定。
    这是更严谨的做法：清洗阶段不替分析阶段做决定。
""")
    r("  物理合理上限与实际超出情况：")
    r("    %-8s %10s %10s %10s" % ("字段", "上限", "超出行数", "实际最大值"))
    outlier_flag = pd.Series(False, index=df.index)
    for c, limit in PHYSICAL_LIMITS.items():
        if c not in df.columns:
            continue
        over = df[c] > limit
        outlier_flag |= over
        r("    %-8s %10s %10s %10s"
          % (c, format(limit, ","), format(int(over.sum()), ","),
             ("%.1f" % df[c].max()) if df[c].notna().any() else "-"))
    df["is_outlier"] = outlier_flag.astype(int)
    n_out = int(outlier_flag.sum())
    r("")
    r("  标记为异常的行：%s 行 (%.2f%%)" % (format(n_out, ","), n_out / len(df) * 100))

    # ================================================================
    # 修正 5：特征工程
    # ================================================================
    r.title("修正 5：特征工程")

    d = df["datetime"]
    df["year"] = d.dt.year
    df["month"] = d.dt.month
    df["day"] = d.dt.day
    df["hour"] = d.dt.hour
    df["weekday"] = d.dt.weekday          # 0=周一, 6=周日
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["season"] = df["month"].map(season_of)
    df["is_heating"] = df["month"].isin([11, 12, 1, 2, 3]).astype(int)
    df["is_sandstorm"] = (df["sandstorm"] == 1).astype(int)

    r("""
  构造的字段：
    year / month / day / hour   时间维度，用于多粒度聚合
    weekday / is_weekend        星期与周末标志
    season                      季节（春/夏/秋/冬）
    is_heating                  采暖季标志（11月-次年3月）
    is_sandstorm                沙尘暴标志

  【为什么要加 is_heating？】
    冬季 AQI 高有两个原因：一是供暖排放增加，二是逆温导致扩散条件差。
    把「采暖季」单独建成一个变量，分析时就能把这两个原因区分开。
    这就是「特征工程」的意义：把领域知识变成模型能用的变量。
""")
    r("  季节分布：")
    for v, c in df["season"].value_counts().items():
        r("    %-6s %8s" % (v, format(c, ",")))

    # ================================================================
    # 去重
    # ================================================================
    r.title("附加检查：重复记录")
    dup = int(df.duplicated(subset=["city_code", "datetime"]).sum())
    r("")
    r("  按「城市 + 时间」判定重复：%s 行" % format(dup, ","))
    if dup:
        df = df.drop_duplicates(subset=["city_code", "datetime"]).copy()
        r("  已去重，剩余 %s 行" % format(len(df), ","))
    else:
        r("  无重复 —— 每个城市每个小时只有一条记录 [OK]")

    # ================================================================
    # 最终验证
    # ================================================================
    r.title("最终验证：用物理常识反查清洗是否正确")

    r("""
  最关键的一步。清洗完不能只看「没报错」，
  要用一个「结果本该如此」的规律去验证。
  对空气质量数据，最好的验证就是：月度 AQI 应该「冬高夏低」。
""")
    monthly = df.groupby("month")["AQI"].agg(["count", "mean"])
    r("  月度平均 AQI：")
    r("    月份  " + "".join("%7d" % m for m in monthly.index))
    r("    均值  " + "".join("%7.1f" % v for v in monthly["mean"]))

    peak = int(monthly["mean"].idxmax())
    low = int(monthly["mean"].idxmin())
    r("")
    r("  最高月：%d 月 (%.1f)      最低月：%d 月 (%.1f)"
      % (peak, monthly.loc[peak, "mean"], low, monthly.loc[low, "mean"]))
    if peak in (11, 12, 1, 2) and low in (6, 7, 8):
        r("")
        r("  [OK] 通过！呈现标准的「冬高夏低」，日期解析正确。")
    else:
        r("")
        r("  [X] 未通过！曲线不符合季节规律，日期解析可能仍有问题。")

    # ================================================================
    # 保存
    # ================================================================
    r.title("保存清洗结果")
    out_csv = work_path("clean_sample.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8")
    size_mb = os.path.getsize(out_csv) / 1024 / 1024
    r("")
    r("  字段数：%d" % len(df.columns))
    r("  记录数：%s" % format(len(df), ","))
    r("  文件：%s  (%.1f MB)" % (out_csv, size_mb))
    r("")
    r("  最终字段列表：")
    for i, c in enumerate(df.columns, 1):
        r("    %2d. %s" % (i, c))

    r.title("清洗流程小结")
    r("""
  原始 %s 行
    |-- 解析日期（%%d/%%m/%%Y）
    |-- 修正列名对调
    |-- 丢弃 AQI 缺失
    |-- 去重
    +-- 标记异常值
  最终 %s 行

  下一步：python step4_analyze.py  （时空分析，开始出图）
""" % (format(n0, ","), format(len(df), ",")))

    r.close()
    print("\n[OK] 清洗完成，报告已写入 output/report_clean.txt")


if __name__ == "__main__":
    main()
