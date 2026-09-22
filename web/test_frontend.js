/**
 * 前端集成测试：用真实 API 数据执行 app.js 的数据处理逻辑。
 *
 * 【为什么需要这个】
 *   平时验证前端只看三件事：API 能返回数据、静态资源能加载、JS 语法正确。
 *   但**这三件事都不能证明"页面真的能渲染出来"**。
 *
 *   如果 app.js 里读错了字段名（比如把 avgAqi 写成 avgAQI），
 *   API 照样返回 200，语法也没错，而图表会画成空的 —— 从服务端完全看不出来。
 *
 *   实测这个测试抓到过一个真 bug：预测值是浮点数，直接渲染会显示
 *   230.105206748126 这样的十几位小数，页面上很难看。
 *
 * 【怎么做的】
 *   把 echarts 和 DOM 都替换成"记录型桩"，然后真正执行 app.js，
 *   接真实的 http://localhost:8080 接口，最后检查：
 *     1. 执行过程有没有抛异常
 *     2. 每个图表有没有拿到数据（setOption 被调用 + series.data 非空）
 *     3. 卡片文字有没有被真正填入
 *
 * 【用法】
 *   1. 先启动 MySQL 与 Web 服务（run_mysql.ps1 / run_web.ps1）
 *   2. 在本目录执行：node test_frontend.js
 *   3. 退出码 0 表示通过
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const BASE = 'http://localhost:8080';
const APP_JS = path.join(__dirname, 'src', 'main', 'resources', 'static',
    'js', 'app.js');

const errors = [];
const charts = {};
const els = {};

/* ---------------- 桩：DOM ---------------- */
function makeEl(id) {
    return {
        id,
        style: {},
        classList: { add() {}, remove() {}, contains() { return false; } },
        textContent: '',
        innerHTML: '',
        value: '',
        dataset: {},
        scrollIntoView() {},
        appendChild() {},
        querySelectorAll() { return []; },
        set onclick(v) { this._onclick = v; },
        get onclick() { return this._onclick; }
    };
}
global.document = {
    getElementById(id) { return (els[id] = els[id] || makeEl(id)); },
    querySelectorAll() { return []; },
    createElement(tag) { return makeEl(tag); }
};
global.window = { addEventListener() {} };
global.navigator = { userAgent: 'node' };

/* ---------------- 桩：echarts ---------------- */
global.echarts = {
    init(el) {
        const c = { id: el && el.id, options: [], resize() {}, off() {}, on() {} };
        c.setOption = (opt) => { c.options.push(opt); };
        charts[c.id] = c;
        return c;
    },
    registerMap() {},
    graphic: { LinearGradient: function () { return {}; } }
};

/* ---------------- 拦截 fetch，补上 BASE ---------------- */
const realFetch = global.fetch;
global.fetch = (url, opts) => {
    const u = typeof url === 'string' && url.startsWith('/') ? BASE + url : url;
    return realFetch(u, opts);
};

/* ---------------- 执行 app.js ---------------- */
try {
    vm.runInThisContext(fs.readFileSync(APP_JS, 'utf8'), { filename: 'app.js' });
} catch (e) {
    errors.push('执行 app.js 时抛异常: ' + e.message);
}

/* ---------------- 等待异步初始化完成后检查 ---------------- */
function hasSeriesData(opt) {
    const series = opt && opt.series;
    if (!series) return false;
    for (const s of [].concat(series)) {
        if (Array.isArray(s.data) && s.data.length > 0) return true;
    }
    return false;
}

setTimeout(() => {
    console.log('='.repeat(64));
    console.log(' 前端集成测试结果');
    console.log('='.repeat(64));

    if (errors.length) {
        console.log('\n[X] 执行异常：');
        errors.forEach(e => console.log('    ' + e));
    } else {
        console.log('\n[OK] app.js 执行过程无异常');
    }

    const expected = ['map', 'yearly', 'monthly', 'hourly', 'province',
        'pollutant', 'ranking', 'heatmap'];
    console.log('\n图表渲染情况：');
    console.log('  ' + '图表'.padEnd(12) + 'setOption  有数据   条目数');
    console.log('  ' + '-'.repeat(50));

    let ok = 0, bad = 0;
    for (const id of expected) {
        const c = charts[id];
        if (!c) { console.log('  ' + id.padEnd(14) + '[X] 未初始化'); bad++; continue; }
        const opt = c.options[c.options.length - 1];
        const has = hasSeriesData(opt);
        const s0 = opt && opt.series && [].concat(opt.series)[0];
        const n = s0 && Array.isArray(s0.data) ? s0.data.length : '-';
        console.log('  ' + id.padEnd(14) + (c.options.length ? '  ✓    ' : '  ✗    ')
            + (has ? '  ✓    ' : '  ✗    ') + '  ' + n);
        has ? ok++ : bad++;
    }

    console.log('\n顶部卡片：');
    for (const id of ['ov-city', 'ov-record', 'ov-aqi', 'ov-citymin',
        'ov-change', 'ov-mae24', 'ov-acc24']) {
        const t = els[id] ? String(els[id].textContent || els[id].innerHTML) : '(不存在)';
        console.log('  ' + id.padEnd(14) + (t && t !== '-' ? '✓' : '✗') + '  ' + t);
    }

    console.log('\n预测结果表：');
    const body = els['pred-body'];
    if (body && body.innerHTML) {
        const rows = (body.innerHTML.match(/<tr>/g) || []).length;
        console.log('  共 ' + rows + ' 行');
        const first = body.innerHTML.split('</tr>')[0].replace(/\s+/g, ' ');
        console.log('  首行：' + first.slice(0, 140));
        // 检查有没有未格式化的长小数
        const longDecimal = body.innerHTML.match(/\d+\.\d{4,}/);
        if (longDecimal) {
            console.log('  [!] 发现未格式化的长小数：' + longDecimal[0]);
            bad++;
        } else {
            console.log('  ✓ 数值格式正常（无十几位小数）');
        }
    } else {
        console.log('  [X] 未生成任何行');
        bad++;
    }

    console.log('\n' + '='.repeat(64));
    console.log(' 汇总：' + ok + ' 个图表正常，' + bad + ' 个异常');
    console.log('='.repeat(64));
    process.exit(bad > 0 || errors.length ? 1 : 0);
}, 6000);
