package com.gznu.air.entity;

/**
 * 城市维度对象，对应 dim_city 表。
 *
 * <p>说明：系统里只有「城市」这一张结构固定的维表用了实体类；
 * 各类聚合查询（年度趋势、月度分布等）返回的是 Map，
 * 因为它们的字段随图表需求变化，用 Map 更灵活、不必为每张图表建一个类。
 * 生产环境中这些只读查询通常也会定义 DTO，这里按毕设规模做了简化。
 */
public class City {

    private String cityCode;        // 城市编码
    private String cityLabel;       // 城市名称
    private String province;        // 所属省份
    private Double lat;             // 纬度
    private Double lon;             // 经度
    private Double avgAqi;          // 五年平均 AQI
    private Double avgPm25;
    private Double avgPm10;
    private Double avgSo2;
    private Double avgNo2;
    private Double avgCo;
    private Double avgO3;
    private Integer recordCount;
    private String pollutionType;   // 污染分型：沙尘型 / 燃烧型 / 一般型 / 清洁型
    private Integer clusterId;      // K-Means 聚类编号

    public String getCityCode() { return cityCode; }
    public void setCityCode(String cityCode) { this.cityCode = cityCode; }

    public String getCityLabel() { return cityLabel; }
    public void setCityLabel(String cityLabel) { this.cityLabel = cityLabel; }

    public String getProvince() { return province; }
    public void setProvince(String province) { this.province = province; }

    public Double getLat() { return lat; }
    public void setLat(Double lat) { this.lat = lat; }

    public Double getLon() { return lon; }
    public void setLon(Double lon) { this.lon = lon; }

    public Double getAvgAqi() { return avgAqi; }
    public void setAvgAqi(Double avgAqi) { this.avgAqi = avgAqi; }

    public Double getAvgPm25() { return avgPm25; }
    public void setAvgPm25(Double avgPm25) { this.avgPm25 = avgPm25; }

    public Double getAvgPm10() { return avgPm10; }
    public void setAvgPm10(Double avgPm10) { this.avgPm10 = avgPm10; }

    public Double getAvgSo2() { return avgSo2; }
    public void setAvgSo2(Double avgSo2) { this.avgSo2 = avgSo2; }

    public Double getAvgNo2() { return avgNo2; }
    public void setAvgNo2(Double avgNo2) { this.avgNo2 = avgNo2; }

    public Double getAvgCo() { return avgCo; }
    public void setAvgCo(Double avgCo) { this.avgCo = avgCo; }

    public Double getAvgO3() { return avgO3; }
    public void setAvgO3(Double avgO3) { this.avgO3 = avgO3; }

    public Integer getRecordCount() { return recordCount; }
    public void setRecordCount(Integer recordCount) { this.recordCount = recordCount; }

    public String getPollutionType() { return pollutionType; }
    public void setPollutionType(String pollutionType) { this.pollutionType = pollutionType; }

    public Integer getClusterId() { return clusterId; }
    public void setClusterId(Integer clusterId) { this.clusterId = clusterId; }
}
