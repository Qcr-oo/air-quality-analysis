# -*- coding: utf-8 -*-
"""
第 7 步：建 MySQL 库表并导入分析结果（第三阶段）

【这一步做什么】
    把 Spark 算出来的聚合结果写进 MySQL，供后面的 Web 系统查询。
    —— 分析结果和展示系统之间需要一个存储层，这就是它。

【为什么不全量导入 1233 万条明细？】
    明细数据 1233 万行导进 MySQL 会让库膨胀到几 GB，而前端展示只需要
    聚合后的结果（地图看城市均值、热力图看城市×月均值）。
    所以这里导入的是【聚合表】，粒度对应每张图表的需求。
    这也是数仓里的常规做法：明细留在数据湖，聚合结果进关系库供查询。

【MySQL 连接说明】
    本项目用的是【独立实例】：数据目录在 F:\\myprogect\\.tools\\mysql-data，
    端口 3307，不影响系统里原有的 MySQL 服务（端口 3306）。
    启动命令见 README 或 run_mysql.ps1。

运行：
    python step7_mysql.py
产出：
    MySQL 数据库 air_quality（11 张表）
    output/report_mysql.txt
"""
import os
import sys

import pandas as pd
import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Reporter
from config import OUT_DIR, out_path, work_path

# ---------------- 数据库连接配置 ----------------
DB_HOST = "127.0.0.1"
DB_PORT = 3307
DB_USER = "root"
DB_PASSWORD = "123456"
DB_NAME = "air_quality"

# ---------------- 建表语句 ----------------
DDL = [
    ("dim_city", """
CREATE TABLE IF NOT EXISTS dim_city (
    city_code   VARCHAR(12)  NOT NULL COMMENT '城市编码',
    city_label  VARCHAR(40)           COMMENT '城市名称',
    province    VARCHAR(40)           COMMENT '所属省份',
    lat         DOUBLE                COMMENT '纬度',
    lon         DOUBLE                COMMENT '经度',
    avg_aqi     DOUBLE                COMMENT '五年平均 AQI',
    avg_pm25    DOUBLE                COMMENT '平均 PM2.5',
    avg_pm10    DOUBLE                COMMENT '平均 PM10',
    avg_so2     DOUBLE, avg_no2 DOUBLE, avg_co DOUBLE, avg_o3 DOUBLE,
    record_count INT                  COMMENT '记录条数',
    pollution_type VARCHAR(20)        COMMENT '污染分型（沙尘型/燃烧型/一般型/清洁型）',
    cluster_id  INT                   COMMENT 'K-Means 聚类编号',
    PRIMARY KEY (city_code),
    KEY idx_province (province),
    KEY idx_aqi (avg_aqi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市维度表'
"""),
    ("agg_national_year", """
CREATE TABLE IF NOT EXISTS agg_national_year (
    year        INT NOT NULL COMMENT '年份',
    avg_aqi     DOUBLE COMMENT '平均 AQI',
    median_aqi  DOUBLE COMMENT '中位 AQI',
    record_count BIGINT COMMENT '记录数',
    PRIMARY KEY (year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全国年度聚合（固定 159 城）'
"""),
    ("agg_city_year", """
CREATE TABLE IF NOT EXISTS agg_city_year (
    city_code   VARCHAR(12) NOT NULL,
    year        INT NOT NULL,
    avg_aqi     DOUBLE,
    record_count INT,
    PRIMARY KEY (city_code, year),
    KEY idx_year (year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市×年聚合'
"""),
    ("agg_city_month", """
CREATE TABLE IF NOT EXISTS agg_city_month (
    city_code   VARCHAR(12) NOT NULL,
    month       INT NOT NULL,
    avg_aqi     DOUBLE,
    PRIMARY KEY (city_code, month),
    KEY idx_month (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市×月聚合（热力图用）'
"""),
    ("agg_national_month", """
CREATE TABLE IF NOT EXISTS agg_national_month (
    month       INT NOT NULL,
    avg_aqi     DOUBLE,
    PRIMARY KEY (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全国月度聚合'
"""),
    ("agg_hourly", """
CREATE TABLE IF NOT EXISTS agg_hourly (
    hour        INT NOT NULL,
    avg_aqi     DOUBLE,
    record_count BIGINT,
    PRIMARY KEY (hour)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日内小时分布'
"""),
    ("agg_province", """
CREATE TABLE IF NOT EXISTS agg_province (
    province    VARCHAR(40) NOT NULL,
    avg_aqi     DOUBLE,
    record_count BIGINT,
    city_count  INT,
    PRIMARY KEY (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='省份聚合'
"""),
    ("agg_pollutant_season", """
CREATE TABLE IF NOT EXISTS agg_pollutant_season (
    season      VARCHAR(10) NOT NULL,
    pollutant   VARCHAR(12) NOT NULL,
    cnt         BIGINT,
    pct         DOUBLE COMMENT '该污染物在该季节的占比(%)',
    PRIMARY KEY (season, pollutant)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='污染物季节结构'
"""),
    ("agg_city_pollutant", """
CREATE TABLE IF NOT EXISTS agg_city_pollutant (
    city_code   VARCHAR(12) NOT NULL,
    pollutant   VARCHAR(12) NOT NULL,
    n           BIGINT,
    PRIMARY KEY (city_code, pollutant)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市×首要污染物'
"""),
    ("fact_prediction", """
CREATE TABLE IF NOT EXISTS fact_prediction (
    id             BIGINT NOT NULL AUTO_INCREMENT,
    city_label     VARCHAR(40),
    predict_time   DATETIME  COMMENT '预测发起时刻 t',
    current_aqi    DOUBLE    COMMENT 'AQI(t)，预测的起点',
    actual_aqi_t1  DOUBLE    COMMENT 'AQI(t+1) 真实值',
    actual_aqi_t24 DOUBLE    COMMENT 'AQI(t+24) 真实值',
    pred_aqi_t1    DOUBLE    COMMENT '提前 1 小时预测值',
    pred_aqi_t24   DOUBLE    COMMENT '提前 24 小时预测值',
    pred_polluted  TINYINT   COMMENT '预测 t+24 是否污染(1=是)',
    polluted_prob  DOUBLE    COMMENT '预测 t+24 污染概率',
    PRIMARY KEY (id),
    KEY idx_city (city_label),
    KEY idx_time (predict_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型预测结果样例'
"""),
    ("dim_aqi_grade", """
CREATE TABLE IF NOT EXISTS dim_aqi_grade (
    grade_level VARCHAR(4) NOT NULL,
    grade_name  VARCHAR(20),
    aqi_min     INT, aqi_max INT,
    color       VARCHAR(10) COMMENT '国标色值，前端直接用',
    PRIMARY KEY (grade_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AQI 等级码表'
"""),
]

AQI_GRADE_ROWS = [
    ("1", "优", 0, 50, "#00E400"),
    ("2", "良", 51, 100, "#FFFF00"),
    ("3", "轻度污染", 101, 150, "#FF7E00"),
    ("4", "中度污染", 151, 200, "#FF0000"),
    ("5", "重度污染", 201, 300, "#8F3F97"),
    ("6", "严重污染", 301, 9999, "#7E0023"),
]


def connect(with_db=True):
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME if with_db else None,
        charset="utf8mb4", autocommit=True)


def bulk_insert(conn, table, df, r, label):
    """把 DataFrame 批量写入表"""
    if df is None or len(df) == 0:
        r("    %-14s 跳过（无数据）" % label)
        return 0
    cols = list(df.columns)
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (
        table, ",".join("`%s`" % c for c in cols),
        ",".join(["%s"] * len(cols)))
    rows = [tuple(None if pd.isna(v) else v for v in rec)
            for rec in df.itertuples(index=False, name=None)]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM %s" % table)      # 幂等：可重复执行
        cur.executemany(sql, rows)
    r("    %-14s 写入 %s 行" % (label, format(len(rows), ",")))
    return len(rows)


def main():
    r = Reporter(out_path("report_mysql.txt"))
    r.title("第 7 步：建 MySQL 库表并导入结果")

    # ---------- 连接 ----------
    r("")
    r("一、连接数据库")
    r("  目标：%s:%d" % (DB_HOST, DB_PORT))
    try:
        conn0 = connect(with_db=False)
    except Exception as e:
        r("")
        r("  [X] 连接失败：%s" % e)
        r("")
        r("  请先启动独立 MySQL 实例：")
        r("      powershell -File run_mysql.ps1")
        r.close()
        return 1

    with conn0.cursor() as cur:
        cur.execute("SELECT VERSION()")
        ver = cur.fetchone()[0]
        cur.execute("CREATE DATABASE IF NOT EXISTS %s "
                    "DEFAULT CHARSET=utf8mb4" % DB_NAME)
    r("  [OK] 已连接，MySQL 版本 %s" % ver)
    r("  [OK] 数据库 %s 就绪" % DB_NAME)
    conn0.close()

    conn = connect()

    # ---------- 建表 ----------
    r.title("二、建表")
    r("""
  【为什么用「先删后建」而不是 CREATE TABLE IF NOT EXISTS？】
    因为 IF NOT EXISTS 遇到已存在的表会直接跳过 —— 表结构改了也不会生效。
    本项目所有表的数据都来自 output/ 下的 CSV，随时可以重建，
    所以「先删后建」既保证脚本可重复执行（幂等），又能让结构变更立即生效。
    （这是踩过的坑：改了 fact_prediction 的列之后忘了删表，
      结果插入时报 Unknown column。）
""")
    with conn.cursor() as cur:
        for name, ddl in DDL:
            cur.execute("DROP TABLE IF EXISTS %s" % name)
            cur.execute(ddl)
            r("  %-22s [OK] 已重建" % name)

    # ---------- 导入 ----------
    r.title("三、导入数据")

    # 3.1 城市维度（合并聚类结果）
    city = pd.read_csv(out_path("spark_city_agg.csv"), dtype={"city_code": str})
    r("""
  【污染分型用哪一份？】
    项目里有两套聚类结果：
      city_clusters.csv         Step 5（sklearn，k=2 + 比值判型）
      mllib_city_clusters.csv   Step 8（Spark MLlib，k=4）
    两者结论方向一致，但城市数不同。

    《设计方案》承诺的是"用 Spark MLlib 做 K-Means 聚类"，
    所以这里【优先】加载 MLlib 的结果，保证 Web 页面与论文引用的数字一致。
    如果 MLlib 结果不存在（还没跑 step8），才回退到 Step 5 的结果。
""")
    cluster_file, cluster_src = None, None
    for fn, src in [("mllib_city_clusters.csv", "Step 8（Spark MLlib）"),
                    ("city_clusters.csv", "Step 5（scikit-learn）")]:
        p = out_path(fn)
        if os.path.isfile(p):
            cluster_file, cluster_src = p, src
            break

    if cluster_file:
        clus = pd.read_csv(cluster_file, dtype={"city_code": str})
        rename = {}
        if "污染类型" in clus.columns:
            rename["污染类型"] = "pollution_type"
        if "类型" in clus.columns:
            rename["类型"] = "cluster_id"
        if "cluster_id" not in clus.columns and "prediction" in clus.columns:
            rename["prediction"] = "cluster_id"
        clus = clus.rename(columns=rename)
        keep = [c for c in ["city_code", "pollution_type", "cluster_id"]
                if c in clus.columns]
        city = city.merge(clus[keep], on="city_code", how="left")
        r("  已合并污染分型，来源：%s（%s）" % (cluster_src, os.path.basename(cluster_file)))
    else:
        city["pollution_type"] = None
        city["cluster_id"] = None
        r("  [!] 未找到任何聚类结果文件，跳过污染分型")
    bulk_insert(conn, "dim_city", city, r, "dim_city")

    # 3.2 全国年度
    ny = pd.read_csv(out_path("spark_result_yearly.csv"))
    ny = ny.rename(columns={"平均AQI": "avg_aqi", "中位AQI": "median_aqi",
                            "记录数": "record_count"})
    bulk_insert(conn, "agg_national_year", ny[["year", "avg_aqi", "median_aqi",
                                               "record_count"]], r, "agg_national_year")

    # 3.3 城市×年
    cy = pd.read_csv(out_path("spark_city_year.csv"), dtype={"city_code": str})
    bulk_insert(conn, "agg_city_year", cy, r, "agg_city_year")

    # 3.4 城市×月
    cm = pd.read_csv(out_path("spark_city_month.csv"), dtype={"city_code": str})
    bulk_insert(conn, "agg_city_month", cm, r, "agg_city_month")

    # 3.5 全国月度
    # [!] 优先用 spark_monthly.csv —— 那是【真正的全国月度均值】（按记录加权）。
    #     早期版本是从 city_month 取算术平均近似的，与论文引用的数字会有偏差，
    #     导致 Web 图表和论文对不上。只有该文件不存在时才回退到近似算法。
    nat_month_path = out_path("spark_monthly.csv")
    if os.path.isfile(nat_month_path):
        nm = pd.read_csv(nat_month_path)[["month", "avg_aqi"]]
        bulk_insert(conn, "agg_national_month", nm, r, "agg_national_month")
        r("      来源：spark_monthly.csv（真实全国月度均值）")
    else:
        nm = cm.groupby("month")["avg_aqi"].mean().round(2).reset_index()
        bulk_insert(conn, "agg_national_month", nm, r, "agg_national_month")
        r("      [!] 未找到 spark_monthly.csv，回退为各城市月度均值的算术平均")

    # 3.6 小时分布
    hr = pd.read_csv(out_path("spark_hourly.csv"))
    bulk_insert(conn, "agg_hourly", hr, r, "agg_hourly")

    # 3.7 省份
    pv = pd.read_csv(out_path("spark_result_province.csv"))
    pv = pv.rename(columns={"平均AQI": "avg_aqi", "n": "record_count"})
    pv["city_count"] = pv["province"].map(
        city.groupby("province")["city_code"].nunique())
    bulk_insert(conn, "agg_province",
                pv[["province", "avg_aqi", "record_count", "city_count"]], r,
                "agg_province")

    # 3.8 污染物季节结构
    ps = pd.read_csv(out_path("spark_result_pollutant.csv"))
    bulk_insert(conn, "agg_pollutant_season",
                ps[["season", "pollutant", "n", "pct"]].rename(
                    columns={"n": "cnt"}), r, "agg_pollutant_season")

    # 3.9 城市×污染物
    cp = pd.read_csv(out_path("spark_city_pollutant.csv"), dtype={"city_code": str})
    bulk_insert(conn, "agg_city_pollutant", cp, r, "agg_city_pollutant")

    # 3.10 预测结果
    try:
        pr = pd.read_csv(out_path("prediction_sample.csv"), parse_dates=["datetime"])
        # [!] 列语义必须对齐 —— 这是本项目踩过的一个真实 bug：
        #     CSV 里的 AQI 是【当前时刻 t】的值，而 pred_aqi_t24 预测的是【t+24】。
        #     如果把 AQI 当成 "actual" 去和 t+24 的预测比，就是拿不同时刻的两个数
        #     做减法，误差会被严重低估（实测 MAE 从 16.78 变成 13.24）。
        #     所以这里明确拆成三列：current_aqi / actual_aqi_t1 / actual_aqi_t24。
        # [!] 另外不要截断取前 N 条：该 CSV 已由 step5 随机抽样（覆盖全部 31 城），
        #     再按城市排序取头部会重新引入采样偏差。
        pr = pr.rename(columns={
            "datetime": "predict_time",
            "AQI": "current_aqi",
            "AQI_t+1": "actual_aqi_t1",
            "AQI_t+24": "actual_aqi_t24",
            "预测_AQI_t+1": "pred_aqi_t1",
            "预测_AQI_t+24": "pred_aqi_t24",
            "预测污染_t+24": "pred_polluted",
            "污染概率_t+24": "polluted_prob"})
        bulk_insert(conn, "fact_prediction",
                    pr[["city_label", "predict_time", "current_aqi",
                        "actual_aqi_t1", "actual_aqi_t24",
                        "pred_aqi_t1", "pred_aqi_t24",
                        "pred_polluted", "polluted_prob"]],
                    r, "fact_prediction")
    except FileNotFoundError:
        r("    %-14s 跳过（未找到 prediction_sample.csv）" % "fact_prediction")

    # 3.11 等级码表
    grade = pd.DataFrame(AQI_GRADE_ROWS,
                         columns=["grade_level", "grade_name", "aqi_min",
                                  "aqi_max", "color"])
    bulk_insert(conn, "dim_aqi_grade", grade, r, "dim_aqi_grade")

    # ---------- 验证 ----------
    r.title("四、验证（实际查询数据库）")
    checks = [
        ("dim_city", "SELECT COUNT(*) FROM dim_city", "城市数"),
        ("agg_city_year", "SELECT COUNT(*) FROM agg_city_year", "城市×年"),
        ("agg_city_month", "SELECT COUNT(*) FROM agg_city_month", "城市×月"),
        ("agg_national_year", "SELECT COUNT(*) FROM agg_national_year", "年度数"),
        ("fact_prediction", "SELECT COUNT(*) FROM fact_prediction", "预测记录"),
    ]
    with conn.cursor() as cur:
        for _, sql, label in checks:
            cur.execute(sql)
            r("  %-12s %s" % (label, format(cur.fetchone()[0], ",")))

    r("")
    r("  【抽样验证 1】全国年度趋势（应与 Spark 报告一致）")
    with conn.cursor() as cur:
        cur.execute("SELECT year, avg_aqi, median_aqi FROM agg_national_year "
                    "ORDER BY year")
        rows = cur.fetchall()
        for y, a, m in rows:
            r("    %d 年：平均 %.2f  中位 %.2f" % (y, a, m))
        if len(rows) >= 2:
            chg = (rows[-1][1] - rows[0][1]) / rows[0][1] * 100
            r("    五年变化率：%.1f%%（负数为改善）" % chg)

    r("")
    r("  【抽样验证 2】污染最重 5 城（应含河北/新疆城市）")
    with conn.cursor() as cur:
        cur.execute("SELECT city_label, province, avg_aqi, pollution_type "
                    "FROM dim_city ORDER BY avg_aqi DESC LIMIT 5")
        for c, p, a, t in cur.fetchall():
            r("    %-10s %-10s %6.1f  %s" % (c, p, a, t or "-"))

    r("")
    r("  【抽样验证 3】污染物季节结构（应呈现季节反转）")
    with conn.cursor() as cur:
        cur.execute("""SELECT season,
                       MAX(CASE WHEN pollutant='PM25' THEN pct END) AS pm25,
                       MAX(CASE WHEN pollutant='PM10' THEN pct END) AS pm10,
                       MAX(CASE WHEN pollutant='O3'   THEN pct END) AS o3
                       FROM agg_pollutant_season GROUP BY season""")
        r("    季节     PM25      PM10        O3")
        for s, a, b, c in cur.fetchall():
            r("    %-6s %7s%%  %7s%%  %7s%%"
              % (s, a if a is not None else "-",
                 b if b is not None else "-", c if c is not None else "-"))

    r("")
    r("  【抽样验证 4】城市污染分型分布")
    with conn.cursor() as cur:
        cur.execute("""SELECT pollution_type, COUNT(*) AS n, ROUND(AVG(avg_aqi),1) AS aqi
                       FROM dim_city GROUP BY pollution_type ORDER BY n DESC""")
        for t, n, a in cur.fetchall():
            r("    %-10s %3d 城   平均 AQI %s" % (t or "(未标注)", n, a))

    conn.close()

    r.title("五、小结")
    r("""
  数据库：air_quality（11 张表）
  连接：%s:%d  用户 %s

  表结构分为三层，对应数仓的分层思想：
    维度层   dim_city / dim_aqi_grade        —— 「谁」「什么等级」
    聚合层   agg_*                           —— 预计算好的指标，供前端直接查
    事实层   fact_prediction                 —— 模型预测结果明细

  为什么这样分？
    前端每张图表对应一张聚合表，查询就是一句简单的 SELECT，
    不需要 JOIN 和实时聚合 —— 这叫「空间换时间」，
    是数据仓库面向分析查询的常规优化手段。

  下一步：python step8_web.py 或启动 Spring Boot 服务
""" % (DB_HOST, DB_PORT, DB_USER))

    r.close()
    print("\n[OK] MySQL 建库导数据完成，报告见 output/report_mysql.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
