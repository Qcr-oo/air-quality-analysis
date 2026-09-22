# -*- coding: utf-8 -*-
"""
第 4 步：时空分析（出图）

【这一步做什么】
    从三个维度刻画全国空气质量的演变：
      时间维度 —— 年际趋势、月度季节规律、日内小时变化、工作日/周末
      空间维度 —— 省份对比、城市排名
      结构维度 —— 首要污染物构成、采暖季影响、沙尘影响

【画图前必须处理的一件事：中文字体】
    matplotlib 默认字体不含中文，中文标签会显示成方框（口口口）。
    这是新手最常踩的坑之一。解决方式是显式指定一个系统中文字体。

运行：
    python step4_analyze.py
产出：
    output/figures/*.png     图表（可直接放进论文）
    output/report_analyze.txt 分析报告
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")           # 无界面后端，避免弹窗阻塞
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
from config import OUT_DIR, out_path, work_path

FIG_DIR = os.path.join(OUT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# 论文里常见的配色（低饱和度，打印也清楚）
C_MAIN = "#2E5C8A"
C_ACCENT = "#C0504D"
C_GREY = "#7F7F7F"
C_GREEN = "#4F8A5B"


def setup_chinese_font():
    """
    配置 matplotlib 中文字体。

    从多个候选里挑第一个系统里存在的。Windows 上一般有
    微软雅黑 / 黑体 / 宋体，任选其一即可。
    """
    from matplotlib import font_manager
    candidates = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi",
                  "Noto Sans CJK SC", "Source Han Sans SC"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False   # 负号正常显示
            return name
    plt.rcParams["axes.unicode_minus"] = False
    return None


def save(fig, name, r):
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    r("    -> %s" % os.path.basename(path))


def main():
    r = Reporter(out_path("report_analyze.txt"))
    font = setup_chinese_font()

    r.title("第 4 步：时空分析")
    r("")
    r("  中文字体：%s" % (font if font else "[!] 未找到中文字体，图中中文会显示为方框"))

    df = pd.read_csv(work_path("clean_sample.csv"), parse_dates=["datetime"])
    r("  读入：%s 行 x %d 列" % (format(len(df), ","), len(df.columns)))
    r("  时间范围：%s ~ %s"
      % (df["datetime"].min().strftime("%Y-%m-%d"),
         df["datetime"].max().strftime("%Y-%m-%d")))

    # 分析时排除已标记的异常值
    d = df[df["is_outlier"] == 0].copy()
    r("  排除异常值后用于分析：%s 行" % format(len(d), ","))

    # ================================================================
    # 时间维度 1：年际趋势
    # ================================================================
    r.title("时间维度 1：年际趋势")

    # ⚠️ 陷阱 3：跨年对比必须固定城市集合
    years_per_city = d.groupby("city_code")["year"].nunique()
    common_cities = set(years_per_city[years_per_city == 5].index)
    r("")
    r("  [!] 陷阱 3：跨年对比必须固定城市集合")
    r("      全样本城市数：%d" % d["city_code"].nunique())
    r("      五年都出现的城市：%d" % len(common_cities))
    r("      下面所有跨年对比只用这 %d 个城市，否则口径不可比。" % len(common_cities))

    dc = d[d["city_code"].isin(common_cities)]
    yearly = dc.groupby("year")["AQI"].agg(["mean", "median", "max", "count"])
    yearly.columns = ["平均AQI", "中位AQI", "最高AQI", "记录数"]
    r("")
    r("  固定城市集合后的逐年 AQI：")
    r("    年份   平均AQI   中位AQI   最高AQI")
    for y, row in yearly.iterrows():
        r("    %d   %8.1f  %8.1f  %8.1f"
          % (y, row["平均AQI"], row["中位AQI"], row["最高AQI"]))

    first, last = yearly["平均AQI"].iloc[0], yearly["平均AQI"].iloc[-1]
    change = (last - first) / first * 100
    r("")
    r("  五年变化：%.1f -> %.1f ，变化率 %.1f%%"
      % (first, last, change))
    r("  （负数为改善）")

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(yearly.index, yearly["平均AQI"], marker="o", color=C_MAIN,
            linewidth=2, markersize=7, label="平均 AQI")
    ax.plot(yearly.index, yearly["中位AQI"], marker="s", color=C_GREEN,
            linewidth=1.5, markersize=5, linestyle="--", label="中位 AQI")
    for x, y in zip(yearly.index, yearly["平均AQI"]):
        ax.annotate("%.1f" % y, (x, y), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color=C_MAIN)
    ax.set_xlabel("年份")
    ax.set_ylabel("AQI")
    ax.set_title("2014-2018 年全国城市平均 AQI 年际变化（固定 %d 城）" % len(common_cities))
    ax.grid(alpha=0.3, linestyle=":")
    ax.legend(frameon=False)
    ax.set_xticks(list(yearly.index))
    save(fig, "fig1_年际趋势.png", r)

    # ================================================================
    # 时间维度 2：月度季节规律
    # ================================================================
    r.title("时间维度 2：月度季节规律")

    monthly = d.groupby("month")["AQI"].agg(["mean", "count"])
    r("")
    r("  月度平均 AQI：")
    r("    月份  " + "".join("%7d" % m for m in monthly.index))
    r("    均值  " + "".join("%7.1f" % v for v in monthly["mean"]))

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    months = list(monthly.index)
    colors = [C_ACCENT if m in (11, 12, 1, 2, 3) else C_MAIN for m in months]
    bars = ax.bar(months, monthly["mean"], color=colors, width=0.68)
    for b, v in zip(bars, monthly["mean"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, "%.0f" % v,
                ha="center", fontsize=8.5)
    ax.set_xlabel("月份")
    ax.set_ylabel("平均 AQI")
    ax.set_title("月度平均 AQI —— 采暖季（红色）与 非采暖季（蓝色）")
    ax.set_xticks(months)
    ax.grid(alpha=0.25, axis="y", linestyle=":")
    save(fig, "fig2_月度规律.png", r)

    heat = d[d["is_heating"] == 1]["AQI"].mean()
    nonheat = d[d["is_heating"] == 0]["AQI"].mean()
    r("")
    r("  采暖季（11月-次年3月）平均 AQI：%.1f" % heat)
    r("  非采暖季平均 AQI：              %.1f" % nonheat)
    r("  采暖季高出 %.1f%%，说明供暖排放是冬季污染的重要成因之一。"
      % ((heat - nonheat) / nonheat * 100))

    # ================================================================
    # 时间维度 3：日内小时变化
    # ================================================================
    r.title("时间维度 3：日内小时变化")

    hourly = d.groupby("hour")["AQI"].mean()
    peak_h = int(hourly.idxmax())
    low_h = int(hourly.idxmin())
    r("")
    r("  日内最高：%d 时 (%.1f)      日内最低：%d 时 (%.1f)"
      % (peak_h, hourly[peak_h], low_h, hourly[low_h]))
    r("""
  【怎么解释】
    早高峰（7-9 时）和晚高峰（18-21 时）机动车排放集中，
    加之夜间逆温层未散，污染物易累积，所以 AQI 偏高。
    午后气温升高、边界层抬升，扩散条件变好，AQI 回落。
""")
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    ax.plot(hourly.index, hourly.values, marker="o", color=C_MAIN, linewidth=2,
            markersize=4.5)
    ax.fill_between(hourly.index, hourly.values, hourly.min() - 2,
                    color=C_MAIN, alpha=0.12)
    ax.axvspan(7, 9, color=C_ACCENT, alpha=0.12)
    ax.axvspan(18, 21, color=C_ACCENT, alpha=0.12)
    ax.set_xlabel("小时")
    ax.set_ylabel("平均 AQI")
    ax.set_title("日内 AQI 变化（红色区间为早晚高峰）")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(alpha=0.25, linestyle=":")
    save(fig, "fig3_日内变化.png", r)

    # ================================================================
    # 时间维度 4：工作日 vs 周末
    # ================================================================
    r.title("时间维度 4：工作日 vs 周末")
    wk = d.groupby("is_weekend")["AQI"].mean()
    r("")
    r("  工作日平均 AQI：%.1f" % wk.get(0, float("nan")))
    r("  周末平均 AQI：  %.1f" % wk.get(1, float("nan")))
    diff = (wk.get(1, 0) - wk.get(0, 0))
    r("  差值：%+.1f  （%s）"
      % (diff, "周末更低，符合工作日排放更多的预期" if diff < 0
         else "周末反而更高，可能与周末出行增加或气象条件有关"))

    # ================================================================
    # 空间维度：省份对比与城市排名
    # ================================================================
    r.title("空间维度：省份对比与城市排名")

    prov = (d.groupby("province")["AQI"]
            .agg(["mean", "count"])
            .sort_values("mean", ascending=False))
    r("")
    r("  污染最重的 8 个省份：")
    for p, row in prov.head(8).iterrows():
        r("    %-10s 平均 AQI %6.1f   (%s 条记录)"
          % (p, row["mean"], format(int(row["count"]), ",")))
    r("")
    r("  最清洁的 5 个省份：")
    for p, row in prov.tail(5).iterrows():
        r("    %-10s 平均 AQI %6.1f" % (p, row["mean"]))

    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    top = prov.head(15).iloc[::-1]
    ax.barh(top.index, top["mean"], color=C_MAIN, height=0.68)
    for i, (p, row) in enumerate(top.iterrows()):
        ax.text(row["mean"] + 0.8, i, "%.0f" % row["mean"], va="center", fontsize=8.5)
    ax.set_xlabel("平均 AQI")
    ax.set_title("各省平均 AQI 排名（污染最重 15 省）")
    ax.grid(alpha=0.25, axis="x", linestyle=":")
    save(fig, "fig4_省份排名.png", r)

    city = (d.groupby("city_label")["AQI"]
            .agg(["mean", "count"]))
    city = city[city["count"] >= 30]     # 记录太少的城市不参与排名
    city = city.sort_values("mean", ascending=False)
    r("")
    r("  污染最重的 10 个城市（记录数 >= 30）：")
    for c, row in city.head(10).iterrows():
        r("    %-10s %6.1f" % (c, row["mean"]))
    r("")
    r("  最清洁的 10 个城市：")
    for c, row in city.tail(10).iloc[::-1].iterrows():
        r("    %-10s %6.1f" % (c, row["mean"]))

    # ================================================================
    # 结构维度：首要污染物构成
    # ================================================================
    r.title("结构维度：首要污染物构成")

    pol = d[d["main_pollutant"] != ""]["main_pollutant"].value_counts()
    r("")
    r("  首要污染物出现次数（前 8）：")
    total_pol = int(pol.sum())
    for p, n in pol.head(8).items():
        r("    %-14s %8s  (%5.2f%%)"
          % (p, format(int(n), ","), n / total_pol * 100))

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    top_pol = pol.head(6)
    other = pol.iloc[6:].sum()
    if other > 0:
        top_pol = pd.concat([top_pol, pd.Series({"(其他)": other})])
    wedges, texts, autotexts = ax.pie(
        top_pol.values, labels=top_pol.index, autopct="%1.1f%%",
        startangle=100, colors=plt.cm.Blues_r(range(0, 200, 200 // max(1, len(top_pol)))),
        textprops={"fontsize": 9})
    for t in autotexts:
        t.set_fontsize(8.5)
        t.set_color("white")
    ax.set_title("首要污染物构成（剔除空气质量为『优』的记录）")
    save(fig, "fig5_污染物构成.png", r)

    # 分季节看首要污染物
    r("")
    r("  首要污染物随季节的变化（占比 %）：")
    seas_pol = (d[d["main_pollutant"] != ""]
                .groupby(["season", "main_pollutant"]).size()
                .unstack(fill_value=0))
    seas_pol = seas_pol.div(seas_pol.sum(axis=1), axis=0) * 100
    cols = [c for c in ["PM25", "PM10", "O3", "NO2", "SO2"] if c in seas_pol.columns]
    r("    季节   " + "".join("%9s" % c for c in cols))
    for s in ["春季", "夏季", "秋季", "冬季"]:
        if s not in seas_pol.index:
            continue
        r("    %-6s " % s + "".join("%8.1f%%" % seas_pol.loc[s, c] for c in cols))
    r("""
  【怎么解释 —— 这段是论文里的分析亮点】
    PM25 在冬季占比最高：供暖 + 逆温，颗粒物累积。
    O3（臭氧）在夏季占比升高：高温强日照促进光化学反应生成臭氧。
    —— 这叫「污染物结构的季节反转」，是大气环境领域的经典现象。
""")

    # ================================================================
    # 沙尘影响
    # ================================================================
    r.title("附加：沙尘事件的影响")
    ss = d[d["is_sandstorm"] == 1]
    r("")
    r("  沙尘记录：%s 行 (%.2f%%)" % (format(len(ss), ","), len(ss) / len(d) * 100))
    if len(ss):
        r("  沙尘时平均 AQI：%.1f" % ss["AQI"].mean())
        r("  非沙尘时平均：  %.1f" % d[d["is_sandstorm"] == 0]["AQI"].mean())
        r("")
        r("  沙尘最多的 5 个城市：")
        for c, n in ss["city_label"].value_counts().head(5).items():
            r("    %-10s %s 次" % (c, format(int(n), ",")))
        r("")
        r("  沙尘时 PM10 / PM25 比值：%.1f"
          % (ss["PM10"].mean() / ss["PM25"].mean()))
        r("  非沙尘时 PM10 / PM25 比值：%.1f"
          % (d[d["is_sandstorm"] == 0]["PM10"].mean()
             / d[d["is_sandstorm"] == 0]["PM25"].mean()))
        r("""
  【为什么看 PM10/PM25 比值？】
    沙尘主要是粗颗粒物（PM10），所以沙尘天 PM10/PM25 比值会明显升高。
    这是区分「沙尘型污染」与「燃烧型污染（PM25 为主）」的一个判据，
    后面做城市聚类时会用到。
""")

    r.title("完成")
    r("")
    r("  图表目录：%s" % FIG_DIR)
    for f in sorted(os.listdir(FIG_DIR)):
        r("    %s" % f)
    r("")
    r("  下一步：python step5_model.py （机器学习建模）")

    r.close()
    print("\n[OK] 分析完成，图表已生成到 output/figures/")


if __name__ == "__main__":
    main()
