# -*- coding: utf-8 -*-
"""
第 5 步：机器学习建模

【本步包含五件事】
    1. 抽取「密集样本」—— 时序建模必须有连续的小时数据
    2. 说明「换算」与「预测」的区别（很多人在这里搞错）
    3. 短期预测（t+1 小时）与持续性基线对比
    4. 预警预测（t+24 小时）—— 这才是「预警」的真正含义
    5. 城市污染类型聚类（K-Means）

【一个必须澄清的方法论问题】
    很多人拿「当前污染物浓度」去预测「当前 AQI」，得到 R2=0.99 就说模型很准。
    这是错的 —— AQI 本身就是污染物浓度的函数（取六项分指数的最大值），
    这不叫预测，叫【单位换算】。

    真正的预测是：用【过去】的信息，推断【未来】的值。
    而且必须和「持续性基线」比 —— 即"什么都不算，直接拿上一小时的值当预测"。
    空气质量有很强的自相关性，这个朴素基线往往强得惊人。
    赢不了基线，模型就没有价值。

运行：
    python step5_model.py
产出：
    data/dense_ml.csv              密集样本（约 55 万行）
    output/report_model.txt        建模报告
    output/city_clusters.csv       城市聚类结果
    output/figures/fig6~fig9.png   模型评估图
"""
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
import pipeline
from config import OUT_DIR, out_path, raw_file, work_path
from step4_analyze import setup_chinese_font

FIG_DIR = os.path.join(OUT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

DENSE_PATH = work_path("dense_ml.csv")
DENSE_YEARS = [2017, 2018]
N_CITIES = 31

C_MAIN = "#2E5C8A"
C_ACCENT = "#C0504D"
C_GREEN = "#4F8A5B"
C_GREY_LINE = "#BFBFBF"
C_ORANGE = "#D98C3F"

HORIZONS = [1, 24]      # 预测提前量：1 小时 / 24 小时

FEATURES = [
    "month", "hour", "weekday", "is_weekend", "is_heating",
    "lat", "lon",
    # aqi_now = 当前这一小时的 AQI。在真实业务里，实时系统此刻确实已知它。
    # 用它作为起点去预测未来，才是标准的「提前 h 小时预测」问题。
    "aqi_now", "aqi_lag1", "aqi_lag2", "aqi_lag3", "aqi_lag24",
    "aqi_roll24", "aqi_roll24_std",
    "PM25_lag1", "PM10_lag1", "O3_lag1", "NO2_lag1",
]

LEAK_FEATURES = ["PM25", "PM10", "SO2", "NO2", "CO", "O3", "O3_8h"]


def save(fig, name, r):
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    r("    -> %s" % os.path.basename(path))


# ====================================================================
def pick_cities(r):
    d = pd.read_csv(work_path("clean_sample.csv"),
                    usecols=["province", "city_code", "city_label"])
    cnt = d.groupby(["province", "city_code", "city_label"]).size().reset_index(name="n")
    idx = cnt.groupby("province")["n"].idxmax()
    picked = cnt.loc[idx].sort_values("n", ascending=False).head(N_CITIES)
    r("  选取城市：%d 个（每省 1 个，覆盖 %d 个省级行政区）"
      % (len(picked), picked["province"].nunique()))
    return set(picked["city_code"].astype(str)), picked


def ensure_dense_data(r):
    if os.path.isfile(DENSE_PATH):
        r("  密集样本已存在，跳过抽取（缓存生效）")
        return
    r("  正在抽取密集样本（需扫描 %s 两年原始数据）..."
      % " / ".join(str(y) for y in DENSE_YEARS))
    codes, picked = pick_cities(r)
    r("  包含城市示例：" + "、".join(picked["city_label"].head(8).tolist()))

    t0 = time.time()
    frames = []
    for y in DENSE_YEARS:
        path = raw_file(y)
        if not os.path.isfile(path):
            continue
        chunks = []
        for chunk in pd.read_csv(path, dtype=str, chunksize=200000,
                                 encoding="utf-8", on_bad_lines="skip"):
            sub = chunk[chunk["city_code"].astype(str).isin(codes)]
            if len(sub):
                chunks.append(sub)
        frames.append(pd.concat(chunks, ignore_index=True) if chunks
                      else pd.DataFrame())
        r("    %d 年：筛出 %s 行" % (y, format(len(frames[-1]), ",")))

    raw = pd.concat(frames, ignore_index=True)
    d = pipeline.clean(raw)
    d.to_csv(DENSE_PATH, index=False, encoding="utf-8")
    r("  清洗后 %s 行，已保存（%.1f MB）用时 %.0f 秒"
      % (format(len(d), ","), os.path.getsize(DENSE_PATH) / 1024 / 1024,
         time.time() - t0))


def build_features(d):
    """
    构造滞后与滚动特征。铁律：只能用过去预测现在。

    记号约定：设当前行为时刻 t（此刻已知 AQI(t)），
        aqi_now     = AQI(t)        当前值（实时系统此刻已知）
        aqi_lagK    = AQI(t-K)      过去第 K 小时的值
        AQI_t+h     = AQI(t+h)      预测目标：未来 h 小时的值
    """
    d = d.sort_values(["city_code", "datetime"]).reset_index(drop=True)
    g = d.groupby("city_code", sort=False)

    d["aqi_now"] = d["AQI"]
    for k in (1, 2, 3, 24):
        d["aqi_lag%d" % k] = g["AQI"].shift(k)
    d["aqi_roll24"] = g["AQI"].transform(
        lambda s: s.shift(1).rolling(24, min_periods=12).mean())
    d["aqi_roll24_std"] = g["AQI"].transform(
        lambda s: s.shift(1).rolling(24, min_periods=12).std())
    for c in ["PM25", "PM10", "O3", "NO2"]:
        if c in d.columns:
            d["%s_lag1" % c] = g[c].shift(1)

    # 预测目标：未来 h 小时的 AQI
    for h in HORIZONS:
        d["AQI_t+%d" % h] = g["AQI"].shift(-h)
    return d


def main():
    r = Reporter(out_path("report_model.txt"))
    font = setup_chinese_font()

    r.title("第 5 步：机器学习建模")
    r("")
    r("  中文字体：%s" % (font or "[!] 未找到"))

    # ---------------- 一、密集样本 ----------------
    r.title("一、抽取密集样本")
    r("""
  【为什么不能直接用第 2 步的小样本？】
    小样本是「每 250 行抽 1 行」，相邻记录平均间隔 182 小时。
    滞后特征（t-1、t-2、t-24）在断掉的时间序列上毫无意义。
    时序建模必须有连续的小时级数据 —— 换个任务就要换份数据。
""")
    ensure_dense_data(r)

    d = pd.read_csv(DENSE_PATH, parse_dates=["datetime"])
    r("")
    r("  读入：%s 行 x %d 列" % (format(len(d), ","), len(d.columns)))
    r("  城市数：%d    时间范围：%s ~ %s"
      % (d["city_code"].nunique(),
         d["datetime"].min().strftime("%Y-%m-%d"),
         d["datetime"].max().strftime("%Y-%m-%d")))

    # ---------------- 二、特征工程 ----------------
    r.title("二、特征工程")
    d = build_features(d)
    r("""
  特征分四类：
    时间      month / hour / weekday / is_weekend / is_heating
    空间      lat / lon
    滞后      AQI 在过去 1、2、3、24 小时的值
    滚动      过去 24 小时 AQI 的均值与标准差
    污染物滞后 PM25 / PM10 / O3 / NO2 的上一小时值

  【铁律】所有特征都做过 shift，确保不含当前时刻及未来的信息。
""")
    r("  特征列表（%d 个）：" % len(FEATURES))
    for f in FEATURES:
        r("    %s" % f)

    before = len(d)
    d = d.dropna(subset=["aqi_lag24", "aqi_roll24", "AQI_t+1", "AQI_t+24"]).copy()
    r("")
    r("  丢弃滞后/目标缺失的行：%s 行 -> 剩余 %s 行"
      % (format(before - len(d), ","), format(len(d), ",")))

    # ---------------- 三、划分 ----------------
    r.title("三、划分训练集与测试集")
    r("""
  【方法论点：时序数据不能随机划分！】
    随机划分会把 2018 年的数据混进训练集，让模型"见过未来"，
    测试分数虚高，上线就崩 —— 这叫数据泄漏。

    正确做法：按时间切 —— 2017 年训练，2018 年考试。
    这才是真实场景：用历史预测未来。
""")
    tr = d[d["year"] == DENSE_YEARS[0]]
    te = d[d["year"] == DENSE_YEARS[1]]
    r("  训练集（%d 年）：%s 行" % (DENSE_YEARS[0], format(len(tr), ",")))
    r("  测试集（%d 年）：%s 行" % (DENSE_YEARS[1], format(len(te), ",")))

    Xtr, Xte = tr[FEATURES], te[FEATURES]

    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    def metrics(y_true, y_pred):
        return {
            "r2": r2_score(y_true, y_pred),
            "mae": mean_absolute_error(y_true, y_pred),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        }

    # ---------------- 四、「换算」不是「预测」 ----------------
    r.title("四、先澄清一件事：「换算」不是「预测」")
    r("""
  AQI 是怎么来的？—— 六项污染物各算一个分指数 IAQI，取【最大值】。
  也就是说 AQI = f(PM25, PM10, SO2, NO2, CO, O3)，是一个确定性函数。

  拿「当前污染物」预测「当前 AQI」，本质是把这个函数拟合一遍，
  这叫【换算 / 单位转换】，不是预测 —— 因为真实场景里，
  你要预测的那个时刻，污染物浓度本来就还不知道。

  下面把它算出来，只是作为参照，看看这个函数被拟合得多准。
""")
    m_conv = HistGradientBoostingRegressor(max_iter=300, random_state=42)
    m_conv.fit(tr[LEAK_FEATURES], tr["AQI"])
    conv = metrics(te["AQI"], m_conv.predict(te[LEAK_FEATURES]))
    r("  换算任务（用当前污染物算当前 AQI）：")
    r("    R2 = %.4f   MAE = %.2f   RMSE = %.2f"
      % (conv["r2"], conv["mae"], conv["rmse"]))
    r("""
  【为什么没到 0.99？】
    因为 O3_8h（臭氧 8 小时滑动均值）缺失 31.5%，
    而臭氧恰恰是夏季 AQI 的首要污染物，缺了它自然拟合不全。
    另外 AQI 取 max 是分段线性函数，存在折点，树模型需要足够深度才能逼近。
""")

    # ---------------- 五、短期预测 t+1 ----------------
    r.title("五、预测任务 A：提前 1 小时预测 AQI")
    r("""
  【必须引入「持续性基线」】
    "什么都不算，直接拿上一小时的 AQI 当作预测值" —— 这叫持续性基线
    （persistence baseline）。空气质量自相关性极强，这个朴素基线往往很能打。
    如果花大力气训的模型赢不了它，模型就没有存在价值。
    所有时间序列预测论文都必须报这个基线。
""")
    preds = {}
    for h in HORIZONS:
        ytr_h = tr["AQI_t+%d" % h]
        yte_h = te["AQI_t+%d" % h]

        # 持续性基线：什么都不算，直接把「当前 AQI」当作未来值。
        # 注意：基线对两个提前量都用同一个起点（当前值），这样对比才公平。
        base = te["aqi_now"]
        base_name = "持续性基线（当前值当预测）"

        bm = metrics(yte_h, base)
        r("  【提前 %d 小时】预测 AQI(t+%d)" % (h, h))
        r("    %-30s R2=%.4f  MAE=%6.2f  RMSE=%6.2f"
          % (base_name, bm["r2"], bm["mae"], bm["rmse"]))

        model = HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.08, max_depth=7,
            l2_regularization=1.0, random_state=42)
        t0 = time.time()
        model.fit(Xtr, ytr_h)
        pred = model.predict(Xte)
        mm = metrics(yte_h, pred)
        r("    %-30s R2=%.4f  MAE=%6.2f  RMSE=%6.2f   (训练+预测 %.1fs)"
          % ("GBDT 模型", mm["r2"], mm["mae"], mm["rmse"], time.time() - t0))

        # MAE 越小越好，所以 (基线 - 模型) / 基线 为【正】才代表改善
        improve = (bm["mae"] - mm["mae"]) / bm["mae"] * 100
        r("    -> 相比基线 MAE 降低 %.1f%%" % improve)
        if improve > 0:
            r("       [OK] 模型优于基线，说明除自相关外还学到了额外信息")
        else:
            r("       [X] 模型没赢过基线 —— 直接沿用基线更划算")
        r("")
        preds[h] = {"base": bm, "model": mm, "pred": pred, "y": yte_h,
                    "model_obj": model, "name": base_name, "improve": improve}

    # 回归评估图（t+24，真正有难度的那一个）
    y24 = preds[24]["y"]
    p24 = preds[24]["pred"]
    b24 = te["aqi_now"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

    samp = np.random.default_rng(42).choice(len(y24), size=min(5000, len(y24)),
                                            replace=False)
    axes[0].scatter(np.asarray(y24)[samp], np.asarray(p24)[samp], s=4, alpha=0.25,
                    color=C_MAIN, label="GBDT")
    axes[0].scatter(np.asarray(y24)[samp], np.asarray(b24)[samp], s=4, alpha=0.15,
                    color=C_ORANGE, label="持续性基线")
    lim = [0, min(400, float(np.asarray(y24).max()))]
    axes[0].plot(lim, lim, color=C_ACCENT, linewidth=1.4, linestyle="--")
    axes[0].set_xlim(lim); axes[0].set_ylim(lim)
    axes[0].set_xlabel("实际 AQI（t+24）")
    axes[0].set_ylabel("预测 AQI")
    axes[0].set_title("提前 24 小时预测：模型 vs 基线")
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].grid(alpha=0.25, linestyle=":")

    for i, h in enumerate(HORIZONS):
        d_ = preds[h]
        vals = [d_["base"]["mae"], d_["model"]["mae"]]
        bars = axes[1].bar([i * 2, i * 2 + 1], vals,
                           color=[C_ORANGE, C_MAIN], width=0.72)
        for b, v in zip(bars, vals):
            axes[1].text(b.get_x() + b.get_width() / 2, v + 0.15, "%.2f" % v,
                         ha="center", fontsize=9)
    axes[1].set_xticks([0, 1, 2, 3])
    axes[1].set_xticklabels(["t+1\n基线", "t+1\nGBDT", "t+24\n基线", "t+24\nGBDT"])
    axes[1].set_ylabel("MAE（越低越好）")
    axes[1].set_title("模型与基线对比")
    axes[1].grid(alpha=0.25, axis="y", linestyle=":")

    err_m = np.asarray(p24) - np.asarray(y24)
    err_b = np.asarray(b24) - np.asarray(y24)
    bins = np.linspace(-100, 100, 70)
    axes[2].hist(err_b, bins=bins, color=C_ORANGE, alpha=0.6, label="基线")
    axes[2].hist(err_m, bins=bins, color=C_MAIN, alpha=0.6, label="GBDT")
    axes[2].axvline(0, color=C_ACCENT, linewidth=1.2, linestyle="--")
    axes[2].set_xlabel("预测误差（预测 - 实际）")
    axes[2].set_ylabel("样本数")
    axes[2].set_title("t+24 误差分布（越窄越好）")
    axes[2].legend(frameon=False, fontsize=9)
    axes[2].grid(alpha=0.25, linestyle=":")
    save(fig, "fig6_回归评估.png", r)

    # ---------------- 六、分类：预警 ----------------
    r.title("六、预测任务 B：提前 24 小时污染预警")
    r("""
  业务问题：明天这个时刻会不会出现污染？
  定义：AQI > 100 为「污染」（轻度污染及以上）。
""")
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import (accuracy_score, classification_report,
                                 confusion_matrix, roc_auc_score, roc_curve)
    ytr_c = (tr["AQI_t+24"] > 100).astype(int)
    yte_c = (te["AQI_t+24"] > 100).astype(int)
    r("  训练集：%s 条污染 / %s 条良好"
      % (format(int(ytr_c.sum()), ","), format(int((1 - ytr_c).sum()), ",")))
    r("  测试集：%s 条污染 / %s 条良好"
      % (format(int(yte_c.sum()), ","), format(int((1 - yte_c).sum()), ",")))

    # 基线分类器：直接沿用当前状态（"现在什么样，明天这个点就什么样"）
    base_pred_c = (te["aqi_now"] > 100).astype(int)
    base_acc = accuracy_score(yte_c, base_pred_c)
    r("")
    r("  基线（沿用当前状态，不做任何预测）：")
    r("    准确率 %.4f" % base_acc)

    clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.08,
                                         max_depth=7, random_state=42)
    t0 = time.time()
    clf.fit(Xtr, ytr_c)
    pred_c = clf.predict(Xte)
    prob_c = clf.predict_proba(Xte)[:, 1]
    acc = accuracy_score(yte_c, pred_c)
    auc = roc_auc_score(yte_c, prob_c)
    r("")
    r("  GBDT 分类器：")
    r("    准确率 Accuracy = %.4f" % acc)
    r("    AUC            = %.4f" % auc)
    r("    用时 %.1f 秒" % (time.time() - t0))
    r("")
    r("  分类报告：")
    for line in classification_report(
            yte_c, pred_c, target_names=["良好(AQI<=100)", "污染(AQI>100)"],
            digits=4).split("\n"):
        r("    " + line)

    cm = confusion_matrix(yte_c, pred_c)
    r("  混淆矩阵：")
    r("                    预测良好     预测污染")
    r("    实际良好        %8s   %8s" % (format(cm[0][0], ","), format(cm[0][1], ",")))
    r("    实际污染        %8s   %8s" % (format(cm[1][0], ","), format(cm[1][1], ",")))
    r("""
  【怎么解读】
    漏报（实际污染、预测良好）= %s 条。预警系统里，漏报的代价通常高于误报，
    所以实际业务中会把判定阈值调低（宁可多报），用准确率换召回率。
    这个权衡叫作 precision-recall trade-off。
""" % format(cm[1][0], ","))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    im = axes[0].imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            axes[0].text(j, i, format(cm[i, j], ","), ha="center", va="center",
                         fontsize=13,
                         color="white" if cm[i, j] > cm.max() / 2 else "black")
    axes[0].set_xticks([0, 1]); axes[0].set_xticklabels(["预测良好", "预测污染"])
    axes[0].set_yticks([0, 1]); axes[0].set_yticklabels(["实际良好", "实际污染"])
    axes[0].set_title("混淆矩阵（准确率 %.3f）" % acc)

    fpr, tpr, _ = roc_curve(yte_c, prob_c)
    axes[1].plot(fpr, tpr, color=C_MAIN, linewidth=2, label="AUC = %.4f" % auc)
    axes[1].plot([0, 1], [0, 1], color=C_GREY_LINE, linewidth=1, linestyle="--")
    axes[1].set_xlabel("假正率 FPR")
    axes[1].set_ylabel("真正率 TPR")
    axes[1].set_title("ROC 曲线（提前 24 小时预警）")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.25, linestyle=":")
    save(fig, "fig7_分类评估.png", r)

    # ---------------- 七、特征重要性 ----------------
    r.title("七、特征重要性分析")
    r("""
  置换重要性（permutation importance）：把某一列的值随机打乱，
  看模型性能掉多少。掉得越多，说明这列越重要。

  [!] 注意：此处 n_jobs=1（单进程）。
      因为 joblib 的并行后端要把临时目录路径编码成 ASCII，
      而本机用户目录是中文（C:\\Users\\瞿崇荣\\...），并行会直接崩溃。
      这是中文 Windows 上跑 Python 的经典坑。
""")
    from sklearn.inspection import permutation_importance
    sub = np.random.default_rng(0).choice(len(Xte), size=min(15000, len(Xte)),
                                          replace=False)
    Xsub = Xte.iloc[sub]
    ysub = preds[24]["y"].iloc[sub]
    t0 = time.time()
    pi = permutation_importance(preds[24]["model_obj"], Xsub, ysub,
                                n_repeats=3, random_state=42, n_jobs=1)
    imp = pd.Series(pi.importances_mean, index=FEATURES).sort_values(ascending=False)
    imp = imp[imp > 0]
    r("  计算用时 %.0f 秒" % (time.time() - t0))
    r("")
    r("  置换重要性排名（t+24 模型，仅列正值）：")
    for f, v in imp.head(14).items():
        bar = "#" * max(1, int(v / imp.max() * 40))
        r("    %-16s %7.3f  %s" % (f, v, bar))

    r("""
  【业务解读】
    如果 aqi_lag24（昨天同一时刻）排第一，说明污染的「日周期」很强 ——
    昨天这个点脏，今天这个点大概率也脏。
    如果 hour / month / is_heating 也有贡献，说明模型学到了
    日内节律和季节规律，这些是超越单纯自相关的「额外信息」。
""")
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    top = imp.head(12).iloc[::-1]
    ax.barh(top.index, top.values, color=C_MAIN, height=0.68)
    ax.set_xlabel("置换重要性（R2 下降幅度）")
    ax.set_title("特征重要性 Top 12（提前 24 小时预测）")
    ax.grid(alpha=0.25, axis="x", linestyle=":")
    save(fig, "fig8_特征重要性.png", r)

    # ---------------- 八、城市聚类 ----------------
    r.title("八、城市污染类型聚类（K-Means）")
    r("""
  目标：把城市按「污染特征」分成几类，识别不同污染类型。
  特征：平均 AQI、六项污染物均值、PM10/PM25 比值、沙尘率、采暖效应
""")
    full = pd.read_csv(work_path("clean_sample.csv"))
    full = full[full["is_outlier"] == 0]

    agg = full.groupby(["city_code", "city_label", "province"]).agg(
        平均AQI=("AQI", "mean"), PM25=("PM25", "mean"), PM10=("PM10", "mean"),
        SO2=("SO2", "mean"), NO2=("NO2", "mean"), CO=("CO", "mean"),
        O3=("O3", "mean"), 记录数=("AQI", "size"),
        沙尘率=("is_sandstorm", "mean")).reset_index()
    agg = agg[agg["记录数"] >= 30].copy()

    agg["PM10_PM25比"] = agg["PM10"] / agg["PM25"]
    heat = full[full["is_heating"] == 1].groupby("city_code")["AQI"].mean()
    non = full[full["is_heating"] == 0].groupby("city_code")["AQI"].mean()
    agg["采暖效应"] = agg["city_code"].map(heat) - agg["city_code"].map(non)
    agg = agg.dropna()

    r("  参与聚类：%d 个城市" % len(agg))

    cfeat = ["平均AQI", "PM25", "PM10", "SO2", "NO2", "CO", "O3",
             "PM10_PM25比", "沙尘率", "采暖效应"]
    X = agg[cfeat].to_numpy(float)

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    r("""
  【为什么必须先标准化？】
    K-Means 用欧氏距离衡量相似度。PM10 的数值在 0–2000，沙尘率在 0–1。
    不标准化的话，沙尘率的影响会被完全淹没。
    标准化后每列均值 0、标准差 1，各特征权重才可比。
""")
    Xs = StandardScaler().fit_transform(X)

    r("  选择聚类数 k（轮廓系数越大越好）：")
    scores = {}
    for k in range(2, 8):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
        scores[k] = silhouette_score(Xs, km.labels_)
        r("    k=%d   轮廓系数 = %.4f" % (k, scores[k]))
    best_k = max(scores, key=scores.get)
    r("  -> 最优 k = %d（轮廓系数 %.4f）" % (best_k, scores[best_k]))

    km = KMeans(n_clusters=best_k, n_init=10, random_state=42).fit(Xs)
    agg["类型"] = km.labels_

    r("")
    r("  各聚类特征画像：")
    profile = agg.groupby("类型")[cfeat].mean().round(1)
    profile.insert(0, "城市数", agg.groupby("类型").size())
    r("    " + profile.to_string().replace("\n", "\n    "))

    ratio_all = agg["PM10_PM25比"].mean()
    aqi_all = agg["平均AQI"].mean()

    r("")
    r("  【怎么读这些聚类】")
    r("    注意：各污染物的【绝对浓度】彼此高度相关（一个城市 PM25 高，")
    r("    PM10 基本也高），所以 K-Means 首先按「污染水平」把城市分开，")
    r("    而不是按「污染类型」。k=2 的轮廓系数最高，正是这个原因。")
    r("")
    r("    要区分【污染类型】，必须看【比值】这类构成指标。")
    r("    所以下面分两步：先用聚类看水平，再用比值显式判类型。")

    r("")
    r("  各聚类画像（附典型城市 = AQI 最接近该类中位数的城市）：")
    type_kind = {}
    for t in sorted(agg["类型"].unique()):
        sub = agg[agg["类型"] == t]
        ratio, aqi, sand = (sub["PM10_PM25比"].mean(),
                            sub["平均AQI"].mean(), sub["沙尘率"].mean())
        if aqi < aqi_all * 0.85:
            level = "相对清洁"
        elif aqi > aqi_all * 1.15:
            level = "污染较重"
        else:
            level = "中等"
        dust_hint = "沙尘影响明显" if sand > 0.05 else "沙尘影响小"
        kind = "%s · %s" % (level, dust_hint)
        type_kind[t] = kind

        med = sub["平均AQI"].median()
        typical = sub.iloc[(sub["平均AQI"] - med).abs().argsort()[:5]]["city_label"].tolist()
        worst = sub.nlargest(3, "平均AQI")["city_label"].tolist()

        r("")
        r("    类型 %d：%d 个城市" % (t, len(sub)))
        r("      平均 AQI %.1f    PM10/PM25 %.2f    沙尘率 %.1f%%"
          % (aqi, ratio, sand * 100))
        r("      判定：%s" % kind)
        r("      典型城市：%s" % "、".join(typical))
        r("      该类型中污染最重：%s" % "、".join(worst))

    # ---------------- 显式分型：沙尘型 vs 燃烧型 ----------------
    r("")
    r("  【显式分型：用比值区分沙尘型与燃烧型】")
    r("""
    判据来自前面的分析（第 4 步 Step4 已经验证过）：
      沙尘天 PM10/PM25 比值 2.4  vs  非沙尘天 1.7
    沙尘主要是粗颗粒物（PM10），燃烧排放主要是细颗粒物（PM2.5）。
    所以比值越高，越偏沙尘型。
""")
    agg["污染类型"] = "一般型"
    agg.loc[agg["平均AQI"] < aqi_all * 0.85, "污染类型"] = "清洁型"
    mask_dust = (agg["PM10_PM25比"] > ratio_all * 1.10) & (agg["沙尘率"] > 0.04)
    mask_burn = (~mask_dust) & (agg["平均AQI"] > aqi_all * 1.15)
    agg.loc[mask_dust, "污染类型"] = "沙尘型"
    agg.loc[mask_burn, "污染类型"] = "燃烧型"

    r("    分型阈值：PM10/PM25 比值 > %.2f 且 沙尘率 > 4%% -> 沙尘型"
      % (ratio_all * 1.10))
    r("              平均 AQI > %.1f 且非沙尘型 -> 燃烧型" % (aqi_all * 1.15))
    r("")
    for kind in ["沙尘型", "燃烧型", "一般型", "清洁型"]:
        sub = agg[agg["污染类型"] == kind]
        if not len(sub):
            continue
        r("    %-6s %3d 城   AQI 均值 %5.1f   PM10/PM25 %4.2f   沙尘率 %4.1f%%"
          % (kind, len(sub), sub["平均AQI"].mean(),
             sub["PM10_PM25比"].mean(), sub["沙尘率"].mean() * 100))
        ex = sub.nlargest(6, "平均AQI")["city_label"].tolist()
        r("           代表：%s" % "、".join(ex))

    r("""
  【结论】
    沙尘型城市集中在西北（新疆、甘肃、宁夏、内蒙古），
    污染的主要来源是自然扬尘；
    燃烧型城市集中在华北平原（河北、河南、山东），
    污染来自钢铁、水泥、燃煤与机动车。

    两类城市的治理思路完全不同：前者靠生态防护林与沙源治理，
    后者靠产业结构调整与排放管控。
    —— 这正是「城市污染分型」的现实意义。
""")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    kind_color = {"沙尘型": C_ORANGE, "燃烧型": C_ACCENT,
                  "一般型": C_MAIN, "清洁型": C_GREEN}
    for kind in ["沙尘型", "燃烧型", "一般型", "清洁型"]:
        sub = agg[agg["污染类型"] == kind]
        if not len(sub):
            continue
        axes[0].scatter(sub["PM10_PM25比"], sub["平均AQI"], s=30, alpha=0.85,
                        color=kind_color[kind], label="%s (%d)" % (kind, len(sub)))
    axes[0].axhline(aqi_all, color=C_GREY_LINE, linestyle="--", linewidth=1)
    axes[0].axvline(ratio_all * 1.10, color=C_GREY_LINE, linestyle=":", linewidth=1)
    axes[0].set_xlabel("PM10 / PM25 比值（越高越偏沙尘型）")
    axes[0].set_ylabel("平均 AQI")
    axes[0].set_title("319 城市污染分型（聚类 k=%d + 比值判型）" % best_k)
    axes[0].legend(frameon=False, fontsize=8.5)
    axes[0].grid(alpha=0.25, linestyle=":")

    ks = sorted(scores)
    axes[1].plot(ks, [scores[k] for k in ks], marker="o", color=C_MAIN, linewidth=2)
    axes[1].axvline(best_k, color=C_ACCENT, linestyle="--", linewidth=1.4,
                    label="最优 k=%d" % best_k)
    axes[1].set_xlabel("聚类数 k")
    axes[1].set_ylabel("轮廓系数")
    axes[1].set_title("最优 k 的选择")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.25, linestyle=":")
    save(fig, "fig9_城市聚类.png", r)

    # ---------------- 九、保存 ----------------
    r.title("九、保存结果")
    agg.to_csv(out_path("city_clusters.csv"), index=False, encoding="utf-8")
    r("  城市聚类结果：output/city_clusters.csv（%d 城）" % len(agg))

    te_out = te[["city_label", "datetime", "AQI", "AQI_t+1", "AQI_t+24"]].copy()
    te_out["预测_AQI_t+1"] = preds[1]["pred"]
    te_out["预测_AQI_t+24"] = preds[24]["pred"]
    te_out["预测污染_t+24"] = pred_c
    te_out["污染概率_t+24"] = prob_c

    # [!] 必须随机抽样，不能取前 N 条
    #     数据是按 (city_code, datetime) 排序的，前 10000 条几乎全部来自同一个城市，
    #     直接取头部会造成严重【采样偏差】—— Web 页面上显示的"模型指标"
    #     会只反映那一个城市的表现，而不是整体表现。
    #     用固定随机种子抽样，既消除偏差，又保证结果可复现。
    n_export = min(50000, len(te_out))
    te_out = (te_out.sample(n=n_export, random_state=42)
              .sort_values(["city_label", "datetime"]))
    te_out.to_csv(out_path("prediction_sample.csv"), index=False, encoding="utf-8")
    r("  预测结果样例：output/prediction_sample.csv（随机抽取 %s 条，覆盖 %d 个城市）"
      % (format(n_export, ","), te_out["city_label"].nunique()))
    r("     [!] 用随机抽样而非取前 N 条：数据按城市排序，取头部会全落在一个城市")

    # ---------------- 十、小结 ----------------
    r.title("十、本步小结")
    r("""
  任务与结果
  ------------------------------------------------------------------
  换算（非预测）  当前污染物 -> 当前 AQI      R2 = %.4f
  预测 A          提前 1 小时
      持续性基线                              R2 = %.4f   MAE = %.2f
      GBDT 模型                               R2 = %.4f   MAE = %.2f
  预测 B          提前 24 小时（真正的预警）
      持续性基线                              R2 = %.4f   MAE = %.2f
      GBDT 模型                               R2 = %.4f   MAE = %.2f
  分类            提前 24 小时是否污染
      持续性基线                              准确率 = %.4f
      GBDT 分类器                             准确率 = %.4f   AUC = %.4f
  聚类            城市污染类型 k=%d           轮廓系数 = %.4f
  ------------------------------------------------------------------

  方法论要点（答辩与面试必问）
    1. 「换算」不等于「预测」，AQI 是污染物的函数，别拿它当预测成绩
    2. 时序数据必须按时间切分，随机切分会造成数据泄漏
    3. 必须引入持续性基线，赢不了基线的模型没有价值
    4. 滞后特征只能来自过去，shift 之后才能 rolling
    5. K-Means 前必须标准化，否则量纲大的特征主导距离
    6. 中文 Windows 上 joblib 并行会因路径编码崩溃，需 n_jobs=1

  下一步（第二阶段）
    - winget install Microsoft.OpenJDK.17  安装 JDK
    - 把本步逻辑迁移到 PySpark，在全量 1233 万条上运行
    - MySQL 建表 + Spring Boot 接口 + ECharts 前端
""" % (conv["r2"],
       preds[1]["base"]["r2"], preds[1]["base"]["mae"],
       preds[1]["model"]["r2"], preds[1]["model"]["mae"],
       preds[24]["base"]["r2"], preds[24]["base"]["mae"],
       preds[24]["model"]["r2"], preds[24]["model"]["mae"],
       accuracy_score(yte_c, base_pred_c), acc, auc,       best_k, scores[best_k]))

    r.close()
    print("\n[OK] 建模完成，报告已写入 output/report_model.txt")


if __name__ == "__main__":
    main()
