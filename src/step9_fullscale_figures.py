# -*- coding: utf-8 -*-
"""
第 9 步：用【全量口径】数据生成论文用图

【为什么需要这一步 —— 一个真实的一致性问题】
    项目里有两条数据处理链路：
        抽样口径（pandas）  49,017 行   -> step4 生成了 fig1~fig5
        全量口径（PySpark） 1193.6 万行 -> step6 生成了聚合 CSV

    论文里引用的是【全量口径】的数字（这是更权威的结果），
    但 fig1~fig5 是用【抽样口径】画的 —— 两者数值不同，例如：
        图上画的是   2014 = 80.6 -> 2018 = 70.8  (-12.1%)
        论文写的是   2014 = 82.1 -> 2018 = 71.2  (-13.3%)

    评委对照图和文，一眼就能看出不一致。

    所以这一步用全量口径的聚合 CSV 重新绘图，
    输出到 output/figures_full/，与抽样口径的图分开存放。

【命名规则】
    文件名直接对应论文的图号（图 5-1、图 5-2…），方便直接插入论文。

运行：
    python step9_fullscale_figures.py
产出：
    output/figures_full/*.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
from config import OUT_DIR, out_path
from step4_analyze import setup_chinese_font

FIG_DIR = os.path.join(OUT_DIR, "figures_full")
os.makedirs(FIG_DIR, exist_ok=True)

C_MAIN = "#2E5C8A"
C_ACCENT = "#C0504D"
C_GREEN = "#4F8A5B"
C_ORANGE = "#D98C3F"
C_GREY = "#BFBFBF"

AQI_COLORS = ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]


def aqi_color(v):
    """按国标把 AQI 映射成颜色"""
    for i, hi in enumerate([50, 100, 150, 200, 300]):
        if v <= hi:
            return AQI_COLORS[i]
    return AQI_COLORS[5]


def save(fig, name, r):
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    r("    -> %s" % name)


def main():
    r = Reporter(out_path("report_figures.txt"))
    font = setup_chinese_font()

    r.title("第 9 步：全量口径论文用图")
    r("")
    r("  中文字体：%s" % (font or "[!] 未找到"))
    r("  数据来源：output/spark_*.csv（全量口径，已去重）")
    r("  输出目录：output/figures_full/")

    # ================================================================
    # 图 5-1  年际趋势
    # ================================================================
    r.title("图 5-1　全国 AQI 年际变化")
    y = pd.read_csv(out_path("spark_result_yearly.csv"))
    y = y.rename(columns={"平均AQI": "avg", "中位AQI": "median"})
    r("  数据：%s" % "  ".join("%d=%.2f" % (a, b) for a, b in zip(y["year"], y["avg"])))
    chg = (y["avg"].iloc[-1] - y["avg"].iloc[0]) / y["avg"].iloc[0] * 100
    r("  五年变化率：%.1f%%" % chg)

    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(y["year"], y["avg"], marker="o", color=C_MAIN, linewidth=2.2,
            markersize=8, label="平均 AQI")
    ax.plot(y["year"], y["median"], marker="s", color=C_GREEN, linewidth=1.5,
            markersize=5.5, linestyle="--", label="中位 AQI")
    for x, v in zip(y["year"], y["avg"]):
        ax.annotate("%.1f" % v, (x, v), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=9.5, color=C_MAIN)
    ax.set_xlabel("年份")
    ax.set_ylabel("AQI")
    ax.set_title("2014–2018 年全国城市平均 AQI 年际变化（固定 159 城，全量口径）")
    ax.set_xticks(list(y["year"]))
    ax.set_ylim(y["median"].min() - 8, y["avg"].max() + 12)
    ax.grid(alpha=0.3, linestyle=":")
    ax.legend(frameon=False)
    save(fig, "图5-1_年际趋势.png", r)

    # ================================================================
    # 图 5-2  月度规律
    # ================================================================
    r.title("图 5-2　月度分布（采暖季 vs 非采暖季）")
    m = pd.read_csv(out_path("spark_monthly.csv"))
    r("  数据：" + "  ".join("%d月=%.1f" % (a, b) for a, b in zip(m["month"], m["avg_aqi"])))
    peak = m.loc[m["avg_aqi"].idxmax()]
    low = m.loc[m["avg_aqi"].idxmin()]
    r("  最高 %d 月(%.1f)  最低 %d 月(%.1f)"
      % (peak["month"], peak["avg_aqi"], low["month"], low["avg_aqi"]))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    colors = [C_ACCENT if mm in (11, 12, 1, 2, 3) else C_MAIN for mm in m["month"]]
    bars = ax.bar(m["month"], m["avg_aqi"], color=colors, width=0.68)
    for b, v in zip(bars, m["avg_aqi"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, "%.1f" % v,
                ha="center", fontsize=8.5)
    ax.set_xlabel("月份")
    ax.set_ylabel("平均 AQI")
    ax.set_title("月度平均 AQI —— 采暖季（红）与非采暖季（蓝），全量口径")
    ax.set_xticks(list(m["month"]))
    ax.set_ylim(0, m["avg_aqi"].max() * 1.18)
    ax.grid(alpha=0.25, axis="y", linestyle=":")
    save(fig, "图5-2_月度规律.png", r)

    # ================================================================
    # 图 5-3  日内变化
    # ================================================================
    r.title("图 5-3　日内小时变化")
    h = pd.read_csv(out_path("spark_hourly.csv"))
    hi, lo = h.loc[h["avg_aqi"].idxmax()], h.loc[h["avg_aqi"].idxmin()]
    r("  最高 %d 时(%.2f)  最低 %d 时(%.2f)"
      % (hi["hour"], hi["avg_aqi"], lo["hour"], lo["avg_aqi"]))

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(h["hour"], h["avg_aqi"], marker="o", color=C_MAIN, linewidth=2.2,
            markersize=5)
    ax.fill_between(h["hour"], h["avg_aqi"], h["avg_aqi"].min() - 2,
                    color=C_MAIN, alpha=0.13)
    ax.axvspan(7, 9, color=C_ACCENT, alpha=0.12)
    ax.axvspan(18, 21, color=C_ACCENT, alpha=0.12)
    ax.annotate("早高峰", xy=(8, h["avg_aqi"].max()), fontsize=9, color=C_ACCENT,
                ha="center")
    ax.annotate("晚高峰", xy=(19.5, h["avg_aqi"].max()), fontsize=9, color=C_ACCENT,
                ha="center")
    ax.set_xlabel("小时")
    ax.set_ylabel("平均 AQI")
    ax.set_title("日内 AQI 变化（全量口径）")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(alpha=0.25, linestyle=":")
    save(fig, "图5-3_日内变化.png", r)

    # ================================================================
    # 图 5-4  省份排名
    # ================================================================
    r.title("图 5-4　省份 AQI 排名")
    p = pd.read_csv(out_path("spark_result_province.csv"))
    p = p.rename(columns={"平均AQI": "avg"}).sort_values("avg", ascending=False)
    r("  污染最重 5 省：" + "、".join(
        "%s %.1f" % (a, b) for a, b in zip(p["province"].head(5), p["avg"].head(5))))

    fig, ax = plt.subplots(figsize=(7.5, 5.6))
    top = p.head(15).iloc[::-1]
    ax.barh(top["province"], top["avg"], color=[aqi_color(v) for v in top["avg"]],
            height=0.68)
    for i, v in enumerate(top["avg"]):
        ax.text(v + 1, i, "%.1f" % v, va="center", fontsize=8.5)
    ax.set_xlabel("平均 AQI")
    ax.set_title("各省平均 AQI 排名（污染最重 15 省，全量口径）")
    ax.grid(alpha=0.25, axis="x", linestyle=":")
    save(fig, "图5-4_省份排名.png", r)

    # ================================================================
    # 图 5-5  污染物季节结构
    # ================================================================
    r.title("图 5-5　首要污染物季节结构")
    ps = pd.read_csv(out_path("spark_result_pollutant.csv"))
    seasons = ["春季", "夏季", "秋季", "冬季"]
    pols = ["PM25", "PM10", "O3"]
    pol_colors = {"PM25": C_ACCENT, "PM10": C_ORANGE, "O3": C_MAIN}
    piv = ps.pivot_table(index="season", columns="pollutant", values="pct",
                         aggfunc="max").reindex(seasons)
    for s in seasons:
        r("  %s：" % s + "  ".join(
            "%s=%.1f%%" % (c, piv.loc[s, c]) for c in pols if c in piv.columns))

    fig, ax = plt.subplots(figsize=(7, 4.2))
    bottom = np.zeros(len(seasons))
    for c in pols:
        if c not in piv.columns:
            continue
        vals = piv[c].fillna(0).to_numpy()
        ax.bar(seasons, vals, bottom=bottom, color=pol_colors[c], label=c, width=0.55)
        for i, (v, b0) in enumerate(zip(vals, bottom)):
            if v >= 6:
                ax.text(i, b0 + v / 2, "%.1f%%" % v, ha="center", va="center",
                        fontsize=9.5, color="white", fontweight="bold")
        bottom += vals
    ax.set_ylabel("占比 (%)")
    ax.set_ylim(0, 100)
    ax.set_title("首要污染物季节结构（全量口径）—— 冬季 PM2.5 主导、夏季 O3 升高")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    ax.grid(alpha=0.2, axis="y", linestyle=":")
    save(fig, "图5-5_污染物构成.png", r)

    # ================================================================
    # 图 6-1  城市排名
    # ================================================================
    r.title("图 6-1　城市 AQI 排名")
    c = pd.read_csv(out_path("spark_city_agg.csv"), dtype={"city_code": str})
    c = c.sort_values("avg_aqi", ascending=False)
    r("  污染最重 5 城：" + "、".join(
        "%s %.1f" % (a, b) for a, b in zip(c["city_label"].head(5), c["avg_aqi"].head(5))))
    r("  最清洁 5 城：" + "、".join(
        "%s %.1f" % (a, b) for a, b in zip(c["city_label"].tail(5)[::-1],
                                           c["avg_aqi"].tail(5)[::-1])))

    fig, ax = plt.subplots(figsize=(7.5, 5.6))
    top = c.head(20).iloc[::-1]
    ax.barh(top["city_label"], top["avg_aqi"],
            color=[aqi_color(v) for v in top["avg_aqi"]], height=0.68)
    for i, v in enumerate(top["avg_aqi"]):
        ax.text(v + 1.5, i, "%.1f" % v, va="center", fontsize=8.5)
    ax.set_xlabel("平均 AQI")
    ax.set_title("城市平均 AQI 排名 Top 20（全量口径）")
    ax.grid(alpha=0.25, axis="x", linestyle=":")
    save(fig, "图6-1_城市排名.png", r)

    # ================================================================
    # 图 6-2  城市 × 月 热力图
    # ================================================================
    r.title("图 6-2　城市 × 月热力图")
    cm = pd.read_csv(out_path("spark_city_month.csv"), dtype={"city_code": str})
    # [!] 只取 city_label 参与合并 —— 两张表都有 avg_aqi 列，
    #     直接 merge 会生成 avg_aqi_x / avg_aqi_y，导致后面取列报 KeyError。
    cm = cm.merge(c[["city_code", "city_label"]], on="city_code", how="left")
    top40 = c.head(40)["city_code"].tolist()
    sub = cm[cm["city_code"].isin(top40)].copy()
    order = c.head(40).set_index("city_code")["city_label"].to_dict()
    idx = {code: i for i, code in enumerate(top40)}
    sub["yi"] = sub["city_code"].map(idx)

    fig, ax = plt.subplots(figsize=(8.5, 8.6))
    grid = np.full((len(top40), 12), np.nan)
    for _, row in sub.iterrows():
        if 0 <= row["yi"] < len(top40):
            grid[int(row["yi"]), int(row["month"]) - 1] = row["avg_aqi"]
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn_r",
                   vmin=np.nanmin(grid), vmax=np.nanmax(grid))
    ax.set_xticks(range(12))
    ax.set_xticklabels(["%d月" % i for i in range(1, 13)], fontsize=8.5)
    ax.set_yticks(range(len(top40)))
    ax.set_yticklabels([order[x] for x in top40], fontsize=7.5)
    ax.set_title("城市 × 月份 AQI 热力图（污染最重 40 城，全量口径）")
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label("平均 AQI")
    r("  城市数：%d，月份数：12" % len(top40))
    save(fig, "图6-2_城市热力图.png", r)

    # ================================================================
    r.title("完成")
    r("")
    r("  输出目录：%s" % FIG_DIR)
    for f in sorted(os.listdir(FIG_DIR)):
        r("    %s" % f)
    r("""
  【与抽样口径图的区别】
    output/figures/       抽样口径（49,017 行）+ sklearn 建模
    output/figures_full/  全量口径（1193.6 万行）—— 论文引用这一套
""")
    r.close()
    print("\n[OK] 全量口径图已生成到 output/figures_full/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
