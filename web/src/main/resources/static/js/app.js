/* ===================================================================
   全国城市空气质量时空演变分析与预测系统 —— 前端逻辑
   -------------------------------------------------------------------
   数据流：后端 REST 接口 (JSON)  ->  本文件  ->  ECharts 渲染
   所有图表的数据都来自 MySQL 的聚合表，前端不做任何计算。
   =================================================================== */

/* ---------------- 全局配置 ---------------- */
const AQI_COLORS = ['#00e400', '#ffff00', '#ff7e00', '#ff0000', '#8f3f97', '#7e0023'];
const AQI_BREAKS = [50, 100, 150, 200, 300];
const SEASONS = ['春季', '夏季', '秋季', '冬季'];
const POLLUTANTS = ['PM25', 'PM10', 'O3', 'NO2', 'SO2'];

/** 按国标把 AQI 数值转成颜色 */
function aqiColor(v) {
    if (v == null) return '#666';
    for (let i = 0; i < AQI_BREAKS.length; i++) {
        if (v <= AQI_BREAKS[i]) return AQI_COLORS[i];
    }
    return AQI_COLORS[5];
}

/** 按国标把 AQI 转成等级名 */
function aqiGrade(v) {
    if (v == null) return '-';
    if (v <= 50) return '优';
    if (v <= 100) return '良';
    if (v <= 150) return '轻度污染';
    if (v <= 200) return '中度污染';
    if (v <= 300) return '重度污染';
    return '严重污染';
}

/** 统一的接口调用：拿 code/msg/data 结构 */
async function api(path) {
    const resp = await fetch('/api' + path);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const json = await resp.json();
    if (json.code !== 200) throw new Error(json.msg || '接口返回异常');
    return json.data;
}

/** 通用图表初始化（统一深色主题） */
function makeChart(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    window.addEventListener('resize', () => chart.resize());
    return chart;
}

const AXIS_STYLE = {
    axisLine: { lineStyle: { color: '#3a4a5e' } },
    axisLabel: { color: '#8b9bb0', fontSize: 11 },
    splitLine: { lineStyle: { color: '#1e2b3a' } }
};
const BASE = {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Microsoft YaHei, sans-serif' },
    tooltip: {
        backgroundColor: 'rgba(22,32,46,.95)',
        borderColor: '#243447',
        textStyle: { color: '#e6edf3', fontSize: 12 }
    }
};

/* ===================================================================
   1. 概览卡片
   =================================================================== */
async function loadOverview() {
    const d = await api('/overview');
    const fmt = n => (n == null ? '-' : Number(n).toLocaleString('en-US'));

    document.getElementById('ov-city').textContent = fmt(d.cityCount);
    document.getElementById('ov-record').innerHTML =
        (d.recordCount / 10000).toFixed(0) + ' <small>万条</small>';
    document.getElementById('ov-aqi').textContent = d.avgAqi;

    const chg = d.fiveYearChange;
    const el = document.getElementById('ov-change');
    el.textContent = (chg > 0 ? '+' : '') + chg + '%';
    el.className = 'value ' + (chg < 0 ? 'good' : 'bad');
    document.getElementById('ov-change-note').textContent =
        chg < 0 ? '空气质量改善' : '空气质量恶化';

    // 模型指标
    document.getElementById('ov-mae24').textContent = d.model.maeT24;
    document.getElementById('ov-acc24').textContent = d.model.accuracyT24 + '%';

    document.getElementById('ov-citymin').textContent =
        d.minAqi + ' ~ ' + d.maxAqi;
}

/* ===================================================================
   2. 全国城市 AQI 地图
   =================================================================== */
let mapChart = null;
let cityData = [];

async function loadMap(typeFilter) {
    mapChart = mapChart || makeChart('map');
    if (!mapChart) return;

    const path = typeFilter ? '/cities?type=' + encodeURIComponent(typeFilter) : '/cities';
    cityData = await api(path);

    document.getElementById('map-count').textContent = cityData.length;

    const points = cityData.map(c => ({
        name: c.cityLabel,
        value: [c.lon, c.lat, c.avgAqi],
        province: c.province,
        type: c.pollutionType,
        code: c.cityCode
    }));

    mapChart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip,
            formatter: p => {
                const d = p.data;
                if (!d) return '';
                return `<b>${d.name}</b>　${d.province || ''}<br/>`
                    + `平均 AQI：<b style="color:${aqiColor(d.value[2])}">${d.value[2]}</b>`
                    + `（${aqiGrade(d.value[2])}）<br/>`
                    + `污染分型：${d.type || '未标注'}<br/>`
                    + `<span style="color:#8b9bb0">点击查看该城市详情</span>`;
            }
        },
        geo: {
            map: 'china',
            roam: true,
            zoom: 1.18,
            label: { show: false },
            itemStyle: {
                areaColor: '#1b2a3d',
                borderColor: '#33506e',
                borderWidth: 0.7
            },
            emphasis: {
                itemStyle: { areaColor: '#25384f' },
                label: { show: false }
            }
        },
        visualMap: {
            type: 'piecewise',
            left: 10, bottom: 10,
            orient: 'vertical',
            textStyle: { color: '#8b9bb0', fontSize: 11 },
            pieces: [
                { min: 301, label: '严重污染 (>300)', color: AQI_COLORS[5] },
                { min: 201, max: 300, label: '重度污染 (201-300)', color: AQI_COLORS[4] },
                { min: 151, max: 200, label: '中度污染 (151-200)', color: AQI_COLORS[3] },
                { min: 101, max: 150, label: '轻度污染 (101-150)', color: AQI_COLORS[2] },
                { min: 51, max: 100, label: '良 (51-100)', color: AQI_COLORS[1] },
                { max: 50, label: '优 (0-50)', color: AQI_COLORS[0] }
            ]
        },
        series: [{
            name: '城市空气质量',
            type: 'scatter',
            coordinateSystem: 'geo',
            data: points,
            symbolSize: v => Math.max(4, Math.min(16, v[2] / 9)),
            itemStyle: {
                color: p => aqiColor(p.value[2]),
                opacity: 0.88,
                borderColor: 'rgba(255,255,255,.35)',
                borderWidth: 0.5
            },
            emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 1.5 } }
        }]
    }, true);

    // 点击城市 -> 显示详情
    mapChart.off('click');
    mapChart.on('click', p => {
        if (p.data && p.data.code) showCityDetail(p.data.code, p.data.name);
    });
}

/* ===================================================================
   3. 城市详情（点击地图触发）
   =================================================================== */
let detailChart = null;

async function showCityDetail(code, name) {
    const panel = document.getElementById('detail-panel');
    panel.style.display = '';
    document.getElementById('detail-title').textContent = name + ' —— 年度趋势与月度分布';

    const d = await api('/city/' + code);
    detailChart = detailChart || makeChart('detail');
    detailChart.resize();

    const years = d.yearly.map(x => x.year);
    const yearAqi = d.yearly.map(x => x.avgAqi);

    detailChart.setOption({
        ...BASE,
        tooltip: { ...BASE.tooltip, trigger: 'axis' },
        legend: { data: ['年度平均 AQI', '月度平均 AQI'], textStyle: { color: '#8b9bb0' }, top: 0 },
        grid: { left: 45, right: 20, top: 36, bottom: 30 },
        xAxis: [
            { type: 'category', data: years, name: '年', ...AXIS_STYLE },
            { type: 'category', data: d.monthly.map(x => x.month + '月'), name: '月',
              position: 'bottom', offset: 0, show: false, ...AXIS_STYLE }
        ],
        yAxis: { type: 'value', name: 'AQI', ...AXIS_STYLE },
        series: [
            {
                name: '年度平均 AQI', type: 'line', data: yearAqi,
                smooth: true, symbolSize: 8, lineStyle: { width: 2.5, color: '#3d8bfd' },
                itemStyle: { color: '#3d8bfd' },
                label: { show: true, color: '#8b9bb0', fontSize: 11 }
            },
            {
                name: '月度平均 AQI', type: 'bar', xAxisIndex: 1,
                data: d.monthly.map(x => x.avgAqi),
                itemStyle: { color: p => aqiColor(p.value) }, barWidth: '55%'
            }
        ]
    }, true);

    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ===================================================================
   4. 年度趋势
   =================================================================== */
async function loadYearly() {
    const chart = makeChart('yearly');
    const d = await api('/national/yearly');

    chart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip, trigger: 'axis',
            formatter: ps => {
                const p = ps[0];
                return `<b>${p.axisValue} 年</b><br/>平均 AQI：<b>${p.data}</b><br/>`
                    + `中位 AQI：${d[p.dataIndex].medianAqi}<br/>`
                    + `记录数：${Number(d[p.dataIndex].recordCount).toLocaleString('en-US')}`;
            }
        },
        grid: { left: 50, right: 24, top: 24, bottom: 30 },
        xAxis: { type: 'category', data: d.map(x => x.year), ...AXIS_STYLE },
        yAxis: { type: 'value', name: 'AQI', min: 60, ...AXIS_STYLE },
        series: [
            {
                type: 'line', data: d.map(x => x.avgAqi), smooth: true,
                symbolSize: 9, lineStyle: { width: 3, color: '#3d8bfd' },
                itemStyle: { color: '#3d8bfd' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(61,139,253,.35)' },
                        { offset: 1, color: 'rgba(61,139,253,0)' }
                    ])
                },
                label: { show: true, color: '#e6edf3', fontSize: 12, fontWeight: 'bold' }
            },
            {
                type: 'line', data: d.map(x => x.medianAqi), smooth: true,
                symbolSize: 6, lineStyle: { width: 1.5, color: '#4f8a5b', type: 'dashed' },
                itemStyle: { color: '#4f8a5b' }, name: '中位数'
            }
        ]
    });
}

/* ===================================================================
   5. 月度分布（采暖季高亮）
   =================================================================== */
async function loadMonthly() {
    const chart = makeChart('monthly');
    const d = await api('/national/monthly');

    chart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip, trigger: 'axis',
            formatter: ps => {
                const p = ps[0];
                const m = d[p.dataIndex].month;
                const heating = [11, 12, 1, 2, 3].includes(m);
                return `<b>${m} 月</b>${heating ? '（采暖季）' : '（非采暖季）'}<br/>`
                    + `平均 AQI：<b style="color:${aqiColor(p.data)}">${p.data}</b>`;
            }
        },
        grid: { left: 50, right: 24, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: d.map(x => x.month + '月'), ...AXIS_STYLE },
        yAxis: { type: 'value', name: 'AQI', ...AXIS_STYLE },
        series: [{
            type: 'bar',
            data: d.map(x => ({
                value: x.avgAqi,
                itemStyle: {
                    color: [11, 12, 1, 2, 3].includes(x.month) ? '#c0504d' : '#2e5c8a',
                    borderRadius: [4, 4, 0, 0]
                }
            })),
            barWidth: '62%',
            label: { show: true, position: 'top', color: '#8b9bb0', fontSize: 10 }
        }]
    });
}

/* ===================================================================
   6. 日内小时分布
   =================================================================== */
async function loadHourly() {
    const chart = makeChart('hourly');
    const d = await api('/hourly');

    chart.setOption({
        ...BASE,
        tooltip: { ...BASE.tooltip, trigger: 'axis' },
        grid: { left: 50, right: 24, top: 24, bottom: 30 },
        xAxis: { type: 'category', data: d.map(x => x.hour + '时'), ...AXIS_STYLE },
        yAxis: { type: 'value', name: 'AQI', scale: true, ...AXIS_STYLE },
        series: [{
            type: 'line', data: d.map(x => x.avgAqi), smooth: true,
            symbolSize: 5, lineStyle: { width: 2.5, color: '#3d8bfd' },
            itemStyle: { color: '#3d8bfd' },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(61,139,253,.3)' },
                    { offset: 1, color: 'rgba(61,139,253,0)' }
                ])
            },
            markArea: {
                silent: true,
                itemStyle: { color: 'rgba(192,80,77,.12)' },
                label: { show: true, color: '#c0504d', fontSize: 10, position: 'top' },
                data: [
                    [{ xAxis: '7时', name: '早高峰' }, { xAxis: '9时' }],
                    [{ xAxis: '18时', name: '晚高峰' }, { xAxis: '21时' }]
                ]
            }
        }]
    });
}

/* ===================================================================
   7. 省份排名
   =================================================================== */
async function loadProvince() {
    const chart = makeChart('province');
    const d = (await api('/provinces')).slice(0, 15).reverse();

    chart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip, trigger: 'axis',
            formatter: ps => {
                const p = ps[0];
                const row = d[p.dataIndex];
                return `<b>${row.province}</b><br/>平均 AQI：<b>${row.avgAqi}</b><br/>`
                    + `城市数：${row.cityCount}<br/>`
                    + `记录数：${Number(row.recordCount).toLocaleString('en-US')}`;
            }
        },
        grid: { left: 90, right: 50, top: 16, bottom: 24 },
        xAxis: { type: 'value', name: 'AQI', ...AXIS_STYLE },
        yAxis: {
            type: 'category', data: d.map(x => x.province),
            ...AXIS_STYLE, axisLabel: { color: '#8b9bb0', fontSize: 11 }
        },
        series: [{
            type: 'bar',
            data: d.map(x => ({ value: x.avgAqi, itemStyle: { color: aqiColor(x.avgAqi) } })),
            barWidth: '62%',
            label: { show: true, position: 'right', color: '#8b9bb0', fontSize: 11 }
        }]
    });
}

/* ===================================================================
   8. 污染物季节结构（堆叠柱状图）
   =================================================================== */
async function loadPollutant() {
    const chart = makeChart('pollutant');
    const raw = await api('/pollutant/season');

    // 转成 {春季: {PM25: 37.5, ...}, ...}
    const bySeason = {};
    SEASONS.forEach(s => bySeason[s] = {});
    raw.forEach(r => {
        if (!bySeason[r.season]) bySeason[r.season] = {};
        bySeason[r.season][r.pollutant] = r.pct;
    });

    const polColors = { PM25: '#c0504d', PM10: '#d98c3f', O3: '#3d8bfd', NO2: '#4f8a5b', SO2: '#8f3f97' };

    chart.setOption({
        ...BASE,
        tooltip: { ...BASE.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: POLLUTANTS, textStyle: { color: '#8b9bb0' }, top: 0, itemWidth: 12, itemHeight: 10 },
        grid: { left: 50, right: 24, top: 34, bottom: 30 },
        xAxis: { type: 'category', data: SEASONS, ...AXIS_STYLE },
        yAxis: { type: 'value', name: '占比 (%)', max: 100, ...AXIS_STYLE },
        series: POLLUTANTS.map(p => ({
            name: p, type: 'bar', stack: 'total',
            data: SEASONS.map(s => bySeason[s][p] || 0),
            itemStyle: { color: polColors[p] },
            barWidth: '55%',
            label: {
                show: true, fontSize: 10, color: '#fff',
                formatter: p2 => (p2.value >= 6 ? p2.value.toFixed(0) + '%' : '')
            }
        }))
    });
}

/* ===================================================================
   9. 城市排名 Top 20
   =================================================================== */
async function loadRanking() {
    const chart = makeChart('ranking');
    const d = await api('/cities');

    const top = d.slice(0, 20).reverse();
    chart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip, trigger: 'axis',
            formatter: ps => {
                const r = top[ps[0].dataIndex];
                return `<b>${r.cityLabel}</b>　${r.province}<br/>`
                    + `平均 AQI：<b style="color:${aqiColor(r.avgAqi)}">${r.avgAqi}</b>`
                    + `（${aqiGrade(r.avgAqi)}）<br/>`
                    + `PM2.5：${r.avgPm25}　PM10：${r.avgPm10}<br/>`
                    + `污染分型：${r.pollutionType || '未标注'}`;
            }
        },
        grid: { left: 80, right: 46, top: 16, bottom: 24 },
        xAxis: { type: 'value', name: 'AQI', ...AXIS_STYLE },
        yAxis: { type: 'category', data: top.map(x => x.cityLabel), ...AXIS_STYLE },
        series: [{
            type: 'bar',
            data: top.map(x => ({
                value: x.avgAqi,
                itemStyle: {
                    color: aqiColor(x.avgAqi),
                    borderRadius: [0, 3, 3, 0]
                }
            })),
            barWidth: '64%',
            label: { show: true, position: 'right', color: '#8b9bb0', fontSize: 11 }
        }]
    });
}

/* ===================================================================
   10. 城市 × 月 热力图（取污染最重的 40 城）
   =================================================================== */
async function loadHeatmap() {
    const chart = makeChart('heatmap');
    const rows = await api('/heatmap');

    // 取平均 AQI 最高的 40 个城市
    const cityAvg = {};
    rows.forEach(r => {
        (cityAvg[r.cityCode] = cityAvg[r.cityCode] || { name: r.cityLabel, sum: 0, n: 0 });
        cityAvg[r.cityCode].sum += r.avgAqi;
        cityAvg[r.cityCode].n++;
    });
    const topCities = Object.keys(cityAvg)
        .map(k => ({ code: k, name: cityAvg[k].name, avg: cityAvg[k].sum / cityAvg[k].n }))
        .sort((a, b) => b.avg - a.avg)
        .slice(0, 40);
    const codeSet = new Set(topCities.map(c => c.code));

    const data = [];
    let maxV = 0;
    rows.forEach(r => {
        if (!codeSet.has(r.cityCode)) return;
        const yi = topCities.findIndex(c => c.code === r.cityCode);
        data.push([r.month - 1, yi, r.avgAqi]);
        if (r.avgAqi > maxV) maxV = r.avgAqi;
    });

    chart.setOption({
        ...BASE,
        tooltip: {
            ...BASE.tooltip, position: 'top',
            formatter: p => `${topCities[p.value[1]].name}　${p.value[0] + 1} 月<br/>`
                + `平均 AQI：<b style="color:${aqiColor(p.value[2])}">${p.value[2]}</b>`
                + `（${aqiGrade(p.value[2])}）`
        },
        grid: { left: 78, right: 20, top: 12, bottom: 56 },
        xAxis: {
            type: 'category', data: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
            splitArea: { show: true }, ...AXIS_STYLE
        },
        yAxis: {
            type: 'category', data: topCities.map(c => c.name),
            splitArea: { show: true }, ...AXIS_STYLE,
            axisLabel: { color: '#8b9bb0', fontSize: 10 }
        },
        visualMap: {
            min: 0, max: Math.ceil(maxV / 20) * 20,
            calculable: true, orient: 'horizontal',
            left: 'center', bottom: 4,
            textStyle: { color: '#8b9bb0', fontSize: 11 },
            inRange: { color: ['#00e400', '#ffff00', '#ff7e00', '#ff0000', '#8f3f97', '#7e0023'] }
        },
        series: [{
            type: 'heatmap', data: data,
            label: { show: false },
            emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,.6)' } }
        }]
    });
}

/* ===================================================================
   11. 预测结果表
   =================================================================== */
async function loadPredictions() {
    const rows = await api('/predictions?limit=300');
    const tbody = document.getElementById('pred-body');
    // [!] 预测值是浮点数，模型输出会有十几位小数（如 230.105206748126）。
    //     直接渲染出来页面会很难看，所以统一保留一位小数。
    const f1 = v => (v == null ? '-' : Number(v).toFixed(1));
    tbody.innerHTML = rows.map(r => {
        const actual24 = r.actualAqiT24, p24 = r.predAqiT24;
        const err = Math.abs(p24 - actual24).toFixed(1);
        // 预警是否正确，要以 t+24 的真实值作标签 —— 不能拿当前值比
        const polluted = r.predPolluted === 1;
        const realPolluted = actual24 > 100;
        const hit = polluted === realPolluted;
        return `<tr>
            <td>${r.cityLabel || '-'}</td>
            <td>${(r.predictTime || '').replace('T', ' ').slice(0, 16)}</td>
            <td>${f1(r.currentAqi)}</td>
            <td style="color:${aqiColor(r.predAqiT1)}">${f1(r.predAqiT1)}</td>
            <td>${f1(actual24)}</td>
            <td style="color:${aqiColor(p24)}">${f1(p24)}</td>
            <td>${err}</td>
            <td><span class="tag ${polluted ? 'bad' : 'ok'}">${polluted ? '污染' : '良好'}</span></td>
            <td>${(r.pollutedProb * 100).toFixed(1)}%</td>
            <td>${hit ? '✓' : '✗'}</td>
        </tr>`;
    }).join('');
}

/* ===================================================================
   12. 污染分型筛选
   =================================================================== */
function bindFilters() {
    const box = document.getElementById('filters');
    const types = ['全部', '沙尘型', '燃烧型', '一般型', '清洁型'];
    box.innerHTML = '<span class="filters-label">污染分型筛选：</span>'
        + types.map((t, i) =>
            `<button data-type="${t}" class="${i === 0 ? 'active' : ''}">${t}</button>`).join('');

    box.querySelectorAll('button').forEach(btn => {
        btn.onclick = async () => {
            box.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const t = btn.dataset.type;
            await loadMap(t === '全部' ? null : t);
        };
    });
}

/* ===================================================================
   启动
   =================================================================== */
(async function init() {
    try {
        // 先注册中国地图，再画图
        const geo = await (await fetch('/js/china.json')).json();
        echarts.registerMap('china', geo);

        await loadOverview();
        await Promise.all([
            loadMap(null),
            loadYearly(),
            loadMonthly(),
            loadHourly(),
            loadProvince(),
            loadPollutant(),
            loadRanking(),
            loadHeatmap(),
            loadPredictions()
        ]);
        bindFilters();

        document.getElementById('loading').classList.add('hide');
    } catch (e) {
        document.getElementById('loading').innerHTML =
            '<div style="text-align:center">' +
            '<div style="color:#ff7e00;font-size:16px;margin-bottom:8px">加载失败</div>' +
            '<div style="font-size:13px">' + e.message + '</div>' +
            '<div style="font-size:12px;margin-top:12px;color:#8b9bb0">' +
            '请确认：1) MySQL 已启动（run_mysql.ps1）　2) 后端服务已启动　3) 已执行 step7_mysql.py' +
            '</div></div>';
        console.error(e);
    }
})();
