package com.gznu.air.mapper;

import com.gznu.air.entity.City;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * 数据访问接口。
 *
 * <p>用 MyBatis 的<b>注解方式</b>写 SQL，不额外维护 XML 映射文件 ——
 * 本项目查询简单（基本都是单表聚合查询），注解更直观、不易出错。
 * 如果 SQL 变复杂（多表 JOIN、动态条件），再拆到 XML 里更合适。
 */
@Mapper
public interface AirQualityMapper {

    // ==================== 维度层 ====================

    /** 全部城市（按 AQI 降序，前端地图与排名榜共用） */
    @Select("SELECT city_code AS cityCode, city_label AS cityLabel, province, "
            + "lat, lon, avg_aqi AS avgAqi, avg_pm25 AS avgPm25, avg_pm10 AS avgPm10, "
            + "avg_so2 AS avgSo2, avg_no2 AS avgNo2, avg_co AS avgCo, avg_o3 AS avgO3, "
            + "record_count AS recordCount, pollution_type AS pollutionType, "
            + "cluster_id AS clusterId "
            + "FROM dim_city ORDER BY avg_aqi DESC")
    List<City> findAllCities();

    /** 按污染分型筛选城市 */
    @Select("SELECT city_code AS cityCode, city_label AS cityLabel, province, "
            + "lat, lon, avg_aqi AS avgAqi, pollution_type AS pollutionType "
            + "FROM dim_city WHERE pollution_type = #{type} ORDER BY avg_aqi DESC")
    List<City> findCitiesByType(@Param("type") String type);

    /** AQI 等级码表（含国标颜色，前端直接用） */
    @Select("SELECT grade_level AS gradeLevel, grade_name AS gradeName, "
            + "aqi_min AS aqiMin, aqi_max AS aqiMax, color "
            + "FROM dim_aqi_grade ORDER BY CAST(grade_level AS UNSIGNED)")
    List<Map<String, Object>> findGrades();

    // ==================== 聚合层 ====================

    /** 全国年度趋势 */
    @Select("SELECT year, avg_aqi AS avgAqi, median_aqi AS medianAqi, "
            + "record_count AS recordCount FROM agg_national_year ORDER BY year")
    List<Map<String, Object>> nationalYearly();

    /** 全国月度分布 */
    @Select("SELECT month, avg_aqi AS avgAqi FROM agg_national_month ORDER BY month")
    List<Map<String, Object>> nationalMonthly();

    /** 日内小时分布 */
    @Select("SELECT hour, avg_aqi AS avgAqi, record_count AS recordCount "
            + "FROM agg_hourly ORDER BY hour")
    List<Map<String, Object>> hourly();

    /** 省份排名 */
    @Select("SELECT province, avg_aqi AS avgAqi, record_count AS recordCount, "
            + "city_count AS cityCount FROM agg_province ORDER BY avg_aqi DESC")
    List<Map<String, Object>> provinces();

    /** 污染物季节结构 */
    @Select("SELECT season, pollutant, cnt, pct FROM agg_pollutant_season "
            + "ORDER BY FIELD(season,'春季','夏季','秋季','冬季'), pct DESC")
    List<Map<String, Object>> pollutantSeason();

    /** 城市×月（热力图用） */
    @Select("SELECT m.city_code AS cityCode, c.city_label AS cityLabel, "
            + "m.month, m.avg_aqi AS avgAqi "
            + "FROM agg_city_month m JOIN dim_city c ON m.city_code = c.city_code "
            + "ORDER BY m.city_code, m.month")
    List<Map<String, Object>> cityMonthly();

    /** 指定城市的年度趋势 */
    @Select("SELECT y.year, y.avg_aqi AS avgAqi, y.record_count AS recordCount "
            + "FROM agg_city_year y WHERE y.city_code = #{cityCode} ORDER BY y.year")
    List<Map<String, Object>> cityYearly(@Param("cityCode") String cityCode);

    /** 指定城市的月度分布 */
    @Select("SELECT month, avg_aqi AS avgAqi FROM agg_city_month "
            + "WHERE city_code = #{cityCode} ORDER BY month")
    List<Map<String, Object>> cityMonthlyByCode(@Param("cityCode") String cityCode);

    /** 指定城市的主要污染物构成 */
    @Select("SELECT pollutant, n FROM agg_city_pollutant "
            + "WHERE city_code = #{cityCode} ORDER BY n DESC")
    List<Map<String, Object>> cityPollutant(@Param("cityCode") String cityCode);

    /** 城市污染分型统计 */
    @Select("SELECT pollution_type AS pollutionType, COUNT(*) AS cityCount, "
            + "ROUND(AVG(avg_aqi),1) AS avgAqi FROM dim_city "
            + "GROUP BY pollution_type ORDER BY cityCount DESC")
    List<Map<String, Object>> pollutionTypeStats();

    // ==================== 事实层 ====================

    /** 预测结果（分页取前 N 条） */
    @Select("SELECT city_label AS cityLabel, predict_time AS predictTime, "
            + "current_aqi AS currentAqi, actual_aqi_t1 AS actualAqiT1, "
            + "actual_aqi_t24 AS actualAqiT24, pred_aqi_t1 AS predAqiT1, "
            + "pred_aqi_t24 AS predAqiT24, pred_polluted AS predPolluted, "
            + "polluted_prob AS pollutedProb "
            + "FROM fact_prediction ORDER BY predict_time LIMIT #{limit}")
    List<Map<String, Object>> predictions(@Param("limit") int limit);

    /**
     * 模型效果统计。
     *
     * <p><b>注意比较对象的时刻必须对齐</b>：
     * <ul>
     *   <li>t+24 的误差 = |pred_aqi_t24 − actual_aqi_t24|，不能拿 current_aqi 去比</li>
     *   <li>预警准确率以 actual_aqi_t24 > 100 作为真实标签</li>
     * </ul>
     * 本项目早期版本误用 current_aqi 作对比基准，导致 MAE 被低估
     * （16.78 被算成 13.24），这是一个典型的「列语义错配」bug。
     */
    @Select("SELECT ROUND(AVG(ABS(pred_aqi_t24 - actual_aqi_t24)), 2) AS maeT24, "
            + "ROUND(AVG(ABS(pred_aqi_t1 - actual_aqi_t1)), 2) AS maeT1, "
            + "ROUND(SUM(CASE WHEN (pred_polluted = 1) = (actual_aqi_t24 > 100) "
            + "THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS accuracyT24, "
            + "ROUND(AVG(ABS(current_aqi - actual_aqi_t24)), 2) AS maeBaseline24, "
            + "COUNT(*) AS n FROM fact_prediction")
    Map<String, Object> modelMetrics();

    // ==================== 概览 ====================

    /** 首页概览数字 */
    @Select("SELECT (SELECT COUNT(*) FROM dim_city) AS cityCount, "
            + "(SELECT COUNT(*) FROM agg_city_month) AS cityMonthCount, "
            + "(SELECT COUNT(DISTINCT province) FROM dim_city) AS provinceCount, "
            + "(SELECT ROUND(AVG(avg_aqi),1) FROM dim_city) AS avgAqi, "
            + "(SELECT ROUND(MIN(avg_aqi),1) FROM dim_city) AS minAqi, "
            + "(SELECT ROUND(MAX(avg_aqi),1) FROM dim_city) AS maxAqi, "
            + "(SELECT SUM(record_count) FROM dim_city) AS recordCount")
    Map<String, Object> overview();

    /** 五年变化率（首年 vs 末年） */
    @Select("SELECT ROUND((MAX(CASE WHEN year = (SELECT MAX(year) FROM agg_national_year) "
            + "THEN avg_aqi END) - MAX(CASE WHEN year = (SELECT MIN(year) FROM agg_national_year) "
            + "THEN avg_aqi END)) / MAX(CASE WHEN year = (SELECT MIN(year) FROM agg_national_year) "
            + "THEN avg_aqi END) * 100, 1) AS changeRate FROM agg_national_year")
    Map<String, Object> fiveYearChange();
}
