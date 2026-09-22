package com.gznu.air.controller;

import com.gznu.air.entity.City;
import com.gznu.air.mapper.AirQualityMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * REST 接口层。
 *
 * <p>统一响应结构 {@code {code, msg, data}}：
 * 前端拿到后先判断 code，再取 data —— 比裸数组更容易处理错误。
 *
 * <p>{@code @RestController} = {@code @Controller} + {@code @ResponseBody}，
 * 方法返回值会被 HttpMessageConverter 序列化成 JSON 写进响应体，
 * 而不是当成视图名去解析模板。
 */
@RestController
@RequestMapping("/api")
public class ApiController {

    @Autowired
    private AirQualityMapper mapper;

    /** 统一封装成功响应 */
    private Map<String, Object> ok(Object data) {
        Map<String, Object> r = new HashMap<>();
        r.put("code", 200);
        r.put("msg", "success");
        r.put("data", data);
        return r;
    }

    /** 统一封装失败响应 */
    private Map<String, Object> fail(int code, String msg) {
        Map<String, Object> r = new HashMap<>();
        r.put("code", code);
        r.put("msg", msg);
        r.put("data", null);
        return r;
    }

    // ==================== 概览 ====================

    /**
     * 首页概览数字。
     * GET /api/overview
     */
    @GetMapping("/overview")
    public Map<String, Object> overview() {
        Map<String, Object> data = new HashMap<>(mapper.overview());
        data.put("fiveYearChange", mapper.fiveYearChange().get("changeRate"));
        data.put("model", mapper.modelMetrics());
        return ok(data);
    }

    // ==================== 城市（地图 / 排名） ====================

    /**
     * 城市列表。可按污染分型筛选。
     * GET /api/cities
     * GET /api/cities?type=沙尘型
     */
    @GetMapping("/cities")
    public Map<String, Object> cities(
            @RequestParam(value = "type", required = false) String type) {
        List<City> list = (type == null || type.trim().isEmpty())
                ? mapper.findAllCities()
                : mapper.findCitiesByType(type.trim());
        return ok(list);
    }

    /**
     * 城市详情：某城市的年度趋势 + 月度分布 + 污染物构成。
     * GET /api/city/110000
     */
    @GetMapping("/city/{cityCode}")
    public Map<String, Object> cityDetail(@PathVariable("cityCode") String cityCode) {
        Map<String, Object> data = new HashMap<>();
        data.put("yearly", mapper.cityYearly(cityCode));
        data.put("monthly", mapper.cityMonthlyByCode(cityCode));
        data.put("pollutant", mapper.cityPollutant(cityCode));
        return ok(data);
    }

    // ==================== 时间维度 ====================

    /** GET /api/national/yearly —— 全国年度趋势 */
    @GetMapping("/national/yearly")
    public Map<String, Object> nationalYearly() {
        return ok(mapper.nationalYearly());
    }

    /** GET /api/national/monthly —— 全国月度分布 */
    @GetMapping("/national/monthly")
    public Map<String, Object> nationalMonthly() {
        return ok(mapper.nationalMonthly());
    }

    /** GET /api/hourly —— 日内小时分布 */
    @GetMapping("/hourly")
    public Map<String, Object> hourly() {
        return ok(mapper.hourly());
    }

    // ==================== 空间维度 ====================

    /** GET /api/provinces —— 省份排名 */
    @GetMapping("/provinces")
    public Map<String, Object> provinces() {
        return ok(mapper.provinces());
    }

    /** GET /api/pollution-types —— 城市污染分型统计 */
    @GetMapping("/pollution-types")
    public Map<String, Object> pollutionTypes() {
        return ok(mapper.pollutionTypeStats());
    }

    // ==================== 结构维度 ====================

    /** GET /api/pollutant/season —— 污染物季节结构 */
    @GetMapping("/pollutant/season")
    public Map<String, Object> pollutantSeason() {
        return ok(mapper.pollutantSeason());
    }

    /** GET /api/grades —— AQI 等级码表（含国标配色） */
    @GetMapping("/grades")
    public Map<String, Object> grades() {
        return ok(mapper.findGrades());
    }

    // ==================== 热力图 ====================

    /**
     * 城市×月 AQI，用于热力图。
     * GET /api/heatmap
     */
    @GetMapping("/heatmap")
    public Map<String, Object> heatmap() {
        return ok(mapper.cityMonthly());
    }

    // ==================== 预测结果 ====================

    /**
     * 模型预测结果样例。
     * GET /api/predictions?limit=200
     */
    @GetMapping("/predictions")
    public Map<String, Object> predictions(
            @RequestParam(value = "limit", defaultValue = "200") int limit) {
        if (limit <= 0 || limit > 20000) {
            return fail(400, "limit 取值需在 1 ~ 20000 之间");
        }
        return ok(mapper.predictions(limit));
    }

    /**
     * 模型效果指标（从数据库实时计算，可复现）。
     * GET /api/model/metrics
     */
    @GetMapping("/model/metrics")
    public Map<String, Object> modelMetrics() {
        return ok(mapper.modelMetrics());
    }
}
