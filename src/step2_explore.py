# -*- coding: utf-8 -*-
"""
第 2 步：数据理解（EDA —— 探索性数据分析）

【这一步在干什么】
    拿到一份数据，先别急着清洗、建模。先「看」。
    看它有几行几列、每列是什么类型、缺多少、取值分布长什么样。
    这是所有数据分析的第一步，行话叫 EDA（Exploratory Data Analysis）。

【EDA 的固定套路 —— 记住这五板斧】
    1. 看形状   df.shape            几行几列？
    2. 看长相   df.head()           前几行长什么样？
    3. 看类型   df.dtypes           每列是数字还是文本？
    4. 看缺失   df.isnull().sum()   哪些列缺、缺多少？
    5. 看分布   df.describe()       数值列的最小/最大/平均？
                df[col].value_counts()  文本列有哪些取值？

运行：
    python step2_explore.py
产出：
    output/report_eda.txt    完整的 EDA 报告
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
from config import POLLUTANT_COLS, SAMPLE_PATH, out_path


def main():
    r = Reporter(out_path("report_eda.txt"))

    r.title("第 2 步：数据理解（EDA）")

    # ---------- 0. 读数据 ----------
    r("")
    r("[0] 读取样本")
    r("  文件：%s" % SAMPLE_PATH)
    df = pd.read_csv(SAMPLE_PATH, dtype=str)   # 全按文本读，避免自动转型出意外
    r("  读入完成：%s 行 x %s 列" % (format(len(df), ","), len(df.columns)))

    # ---------- 1. 看形状 ----------
    r.title("1. 看形状（shape）")
    r("")
    r("df.shape = %s" % (df.shape,))
    r("  -> %s 行数据，%d 个字段" % (format(df.shape[0], ","), df.shape[1]))

    # ---------- 2. 看长相 ----------
    r.title("2. 看长相（head）—— 前 3 行")
    with pd.option_context("display.max_columns", None, "display.width", 250):
        for line in df.head(3).to_string().split("\n"):
            r(line)

    # ---------- 3. 看类型 ----------
    r.title("3. 看类型（dtypes）")
    r("")
    r("全部按文本读入，所以现在都是 object/str。")
    r("这提醒我们一件事：CSV 里所有内容都是字符串，")
    r("「AQI 是数字」这件事，需要我们自己转换（下一步做）。")
    r("")
    for line in df.dtypes.to_string().split("\n"):
        r(line)

    # ---------- 4. 看缺失 ----------
    r.title("4. 看缺失（isnull）")
    miss = df.isnull().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    r("")
    if len(miss) == 0:
        r("  没有 NaN —— 但别高兴太早，往下看空字符串检查。")
    else:
        r("  有 NaN 的列：")
        for col, n in miss.items():
            r("    %-16s %8s 行  (%.2f%%)"
              % (col, format(n, ","), n / len(df) * 100))

    r("")
    r("  [!] 重点：还要检查「空字符串」")
    r("  空字符串不是 NaN，pandas 不会把它算进 isnull()。")
    r("  这是一个非常常见的坑：CSV 里写作  ,,  的空字段会被读成空字符串，")
    r("  只看 isnull() 会以为数据很干净。")
    r("")
    blank = (df == "").sum()
    blank = blank[blank > 0].sort_values(ascending=False)
    if len(blank) == 0:
        r("    没有空字符串。")
    else:
        for col, n in blank.items():
            r("    %-16s %8s 行  (%.2f%%)"
              % (col, format(n, ","), n / len(df) * 100))

    # ---------- 5. 看分布 ----------
    r.title("5. 看数值列分布（describe）")
    num = df.copy()
    for c in POLLUTANT_COLS + ["AQI", "lat", "lon"]:
        if c in num.columns:
            num[c] = pd.to_numeric(num[c], errors="coerce")
    cols = [c for c in POLLUTANT_COLS + ["AQI", "lat", "lon"] if c in num.columns]
    r("")
    for line in num[cols].describe().round(2).to_string().split("\n"):
        r(line)

    r("")
    r("  【怎么读这张表】")
    r("    count    非空值的个数 —— 和总行数比，就知道缺多少")
    r("    mean     平均值")
    r("    std      标准差 —— 越大说明数据越分散")
    r("    min/max  最小/最大值 —— 用来发现异常值")
    r("    50%      中位数 —— 和 mean 差得远，说明分布偏斜")

    # ---------- 6. 看分类列 ----------
    r.title("6. 看文本列的取值（value_counts）")
    for col in ["grade_level", "pollutions", "quality", "sandstorm"]:
        if col not in df.columns:
            continue
        vc = df[col].fillna("(NaN)").replace("", "(空)").value_counts()
        r("")
        r("  【%s】共 %d 种取值，前 8 个：" % (col, len(vc)))
        for v, n in vc.head(8).items():
            r("    %-20s %8s 行" % (v, format(n, ",")))

    # ---------- 7. 空间覆盖 ----------
    r.title("7. 空间覆盖")
    r("")
    r("  省份数：%d" % df["province"].nunique())
    r("  城市数：%d" % df["city_code"].nunique())
    r("")
    r("  各城市出现次数（前 5 / 后 5）：")
    cc = df["city_code"].value_counts()
    r("    最多：" + ", ".join("%s(%d)" % (k, v) for k, v in cc.head(5).items()))
    r("    最少：" + ", ".join("%s(%d)" % (k, v) for k, v in cc.tail(5).items()))
    r("")
    r("  [!] 注意：如果各城市记录数差很多，说明城市覆盖不均匀，")
    r("      做「全国平均」时会被记录多的城市带偏。这是陷阱 3 的伏笔。")

    # ---------- 8. 思考题 ----------
    r.title("思考题（先自己想，再看下一步怎么做）")
    r("""
  1. pollutions 列里装的是什么？quality 列里装的是什么？
     它们的列名和内容对得上吗？

  2. `quality` 列的 NaN 占比是 31%，`pollutions` 列却几乎没有 NaN。
     这暗示这两列是什么关系？

  3. describe() 里，AQI 的 max 是多少？这个值合理吗？
     （提示：国标里 AQI 最高到 500，超过 500 是没有定义的）

  4. 为什么这一步【不】直接把日期转成时间类型？留到下一步做有什么好处？

  5. 如果不用抽样，直接读 1233 万行会怎样？
     估算一下：5.8 MB / 49,017 行 ≈ 每行多少字节？
     乘 1233 万 ≈ 多少 GB？（对照原始文件 1.89 GB）
""")

    r.title("完成")
    r("")
    r("  报告已保存：%s" % out_path("report_eda.txt"))
    r("  下一步：python step3_clean.py  （按 EDA 的发现做清洗）")

    r.close()
    print("\n[OK] EDA 完成，报告已写入 output/report_eda.txt")


if __name__ == "__main__":
    main()
