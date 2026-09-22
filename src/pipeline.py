# -*- coding: utf-8 -*-
"""
数据处理管线：把「原始 DataFrame」变成「干净 DataFrame」的可复用函数。

【为什么单独抽一个模块】
    step3_clean.py 面向教学，把每一步都展开讲透了；
    但 step5_model.py 也需要同一套清洗逻辑。
    如果直接复制一遍，将来改规则就要改两个地方 —— 这是 bug 的温床。
    所以把「纯逻辑」抽到这里，两边共用。

    原则：教学脚本负责「讲清楚」，管线模块负责「可复用」。
"""
import pandas as pd

from config import COL_MAIN_POLLUTANT, COL_QUALITY_DESC, DATE_FORMAT, POLLUTANT_COLS


def parse_datetime(series):
    """
    解析日期列。

    [!] 关键：本数据集是「日/月/年」，不是「月/日/年」。
        用 format 明确指定，errors='coerce' 把失败的变成 NaT 而不是抛异常。
    """
    return pd.to_datetime(series, format=DATE_FORMAT, errors="coerce")


def fix_column_swap(df):
    """
    修正列名与内容对调。

    原始 CSV 中：
        pollutions 列 实际装的是「质量描述」（优/良/轻度污染…）
        quality    列 实际装的是「首要污染物」（PM25/PM10/O3…）

    修正后列名：
        quality_desc      质量描述
        main_pollutant    首要污染物
    """
    df = df.copy()
    if "pollutions" in df.columns:
        df[COL_QUALITY_DESC] = df["pollutions"].fillna("").astype(str).str.strip()
    if "quality" in df.columns:
        df[COL_MAIN_POLLUTANT] = df["quality"].fillna("").astype(str).str.strip()
    drop = [c for c in ("pollutions", "quality") if c in df.columns]
    if drop:
        df = df.drop(columns=drop)
    return df


def to_numeric(df):
    """污染物浓度、AQI、经纬度等列转成数值型"""
    df = df.copy()
    for c in POLLUTANT_COLS + ["AQI", "lat", "lon", "sandstorm"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def add_time_features(df):
    """构造时间维度特征"""
    df = df.copy()
    d = df["datetime"]
    df["year"] = d.dt.year
    df["month"] = d.dt.month
    df["day"] = d.dt.day
    df["hour"] = d.dt.hour
    df["weekday"] = d.dt.weekday
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["season"] = df["month"].map(
        lambda m: "春季" if m in (3, 4, 5) else
                  "夏季" if m in (6, 7, 8) else
                  "秋季" if m in (9, 10, 11) else "冬季")
    # 采暖季：北方 11 月–次年 3 月集中供暖
    df["is_heating"] = df["month"].isin([11, 12, 1, 2, 3]).astype(int)
    df["is_sandstorm"] = (df["sandstorm"] == 1).astype(int)
    return df


def clean(df):
    """
    完整清洗流程：解析日期 -> 修正列名 -> 转数值 -> 去重 -> 加时间特征

    【为什么必须去重 —— 陷阱 5】
        原始数据本身存在重复记录：同一城市、同一时刻出现多行。
        实测（上海 2017 年）：9,036 条记录里只有 8,728 个不同时刻，
        其中 1/1/2017 00:00:00 出现了 32 次 —— 显然是当年数据采集的故障。

        重复记录会造成三个后果：
          1. 记录数虚高，城市均值的权重被扭曲
          2. 被重复的值在算平均时被反复计入，均值发生偏移
          3. 【最严重】破坏时序特征：用 groupby().shift(k) 构造滞后特征时，
             shift 是按【行】移动而不是按【时间】移动。
             有重复行时，"往前 24 行"并不是"24 小时前"，
             滞后特征与目标值的时间间隔就错乱了。
    """
    df = df.copy()
    df["datetime"] = parse_datetime(df["release_date"])
    df = df[df["datetime"].notna()].copy()
    df = fix_column_swap(df)
    df = to_numeric(df)
    df = df[df["AQI"].notna()].copy()

    # 陷阱 5：按「城市 + 时刻」去重，保留第一条
    df = df.drop_duplicates(subset=["city_code", "datetime"], keep="first").copy()

    df = add_time_features(df)
    return df
