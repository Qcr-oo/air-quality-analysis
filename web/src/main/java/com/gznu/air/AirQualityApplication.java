package com.gznu.air;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.ServletComponentScan;

/**
 * 全国城市空气质量时空演变分析与预测系统 —— 启动类
 *
 * <p>毕业设计 Web 可视化模块。数据来源：Spark 离线分析结果已写入 MySQL
 * 数据库 air_quality（见 src/step7_mysql.py）。
 *
 * <p>架构：
 * <pre>
 *   ECharts 前端 (static/)
 *        |  HTTP / JSON
 *   ApiController   —— 接收请求、返回 JSON
 *        |
 *   AirQualityMapper —— MyBatis 注解方式访问数据库
 *        |
 *   MySQL air_quality 库（11 张表：维度层 / 聚合层 / 事实层）
 * </pre>
 *
 * <p>启动后访问：<a href="http://localhost:8080">http://localhost:8080</a>
 */
@SpringBootApplication
@MapperScan("com.gznu.air.mapper")
@ServletComponentScan
public class AirQualityApplication {

    public static void main(String[] args) {
        SpringApplication.run(AirQualityApplication.class, args);
        System.out.println("\n=========================================================");
        System.out.println("  空气质量分析系统已启动");
        System.out.println("  请访问：http://localhost:8080");
        System.out.println("=========================================================\n");
    }
}
