// 状态
let currentCommodity = 'gold';
let currentInterval = '1h';
let chart = null;

// 商品名称映射
const NAMES = {
    gold: '黄金',
    oil: '原油',
    dxy: '美元指数 DXY',
    vix: 'VIX 恐慌指数'
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    chart = echarts.init(document.getElementById('klineChart'));

    // 响应式
    window.addEventListener('resize', () => chart.resize());

    // 左侧栏点击
    document.querySelectorAll('.commodity-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelector('.commodity-item.active').classList.remove('active');
            item.classList.add('active');
            currentCommodity = item.dataset.key;
            document.getElementById('currentTitle').textContent = NAMES[currentCommodity];
            loadData();
        });
    });

    // 周期切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelector('.tab.active').classList.remove('active');
            tab.classList.add('active');
            currentInterval = tab.dataset.interval;
            loadData();
        });
    });

    // 首次加载
    loadData();
    loadPrices();

    // 每30秒刷新价格
    setInterval(loadPrices, 30000);
});

async function loadPrices() {
    try {
        const res = await fetch('/api/prices');
        const prices = await res.json();

        for (const [key, data] of Object.entries(prices)) {
            const priceEl = document.getElementById(`price-${key}`);

            if (priceEl && data.price) {
                priceEl.textContent = data.price.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
        }
    } catch (e) {
        console.error('价格加载失败:', e);
    }
}

async function loadData() {
    const loading = document.getElementById('loading');
    loading.classList.add('show');

    try {
        const res = await fetch(`/api/kline?commodity=${currentCommodity}&interval=${currentInterval}`);
        const data = await res.json();

        if (data.error) {
            alert('数据加载失败: ' + data.error);
            return;
        }

        renderChart(data);
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        loading.classList.remove('show');
    }
}

function renderChart(data) {
    const upColor = '#ef5350';
    const downColor = '#26a69a';

    const option = {
        backgroundColor: '#0a0e17',
        animation: false,
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: '#1e293b',
            borderColor: '#334155',
            textStyle: { color: '#e2e8f0', fontSize: 12 },
            formatter: function (params) {
                const k = params.find(p => p.seriesName === 'K线');
                if (!k) return '';
                const d = k.data;
                return `<b>${k.axisValue}</b><br/>
                    开: ${d[1]}<br/>
                    收: ${d[2]}<br/>
                    低: ${d[3]}<br/>
                    高: ${d[4]}`;
            }
        },
        axisPointer: {
            link: [{ xAxisIndex: [0, 1] }]
        },
        grid: [
            { left: 60, right: 40, top: 30, height: '55%' },
            { left: 60, right: 40, top: '72%', height: '18%' }
        ],
        xAxis: [
            {
                type: 'category',
                data: data.dates,
                gridIndex: 0,
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8', fontSize: 11 },
                splitLine: { show: false }
            },
            {
                type: 'category',
                data: data.dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: { show: false },
                splitLine: { show: false }
            }
        ],
        yAxis: [
            {
                scale: true,
                gridIndex: 0,
                splitArea: { show: false },
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8', fontSize: 11 },
                splitLine: { lineStyle: { color: '#1e293b' } }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: { show: false },
                splitLine: { lineStyle: { color: '#1e293b' } }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 70,
                end: 100
            },
            {
                type: 'slider',
                xAxisIndex: [0, 1],
                bottom: 10,
                height: 20,
                borderColor: '#334155',
                fillerColor: 'rgba(37, 99, 235, 0.2)',
                handleStyle: { color: '#2563eb' },
                textStyle: { color: '#94a3b8' }
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.values,
                itemStyle: {
                    color: upColor,
                    color0: downColor,
                    borderColor: upColor,
                    borderColor0: downColor
                }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: data.volumes,
                itemStyle: {
                    color: function (params) {
                        const i = params.dataIndex;
                        const vals = data.values[i];
                        return vals[1] >= vals[0] ? upColor : downColor;
                    }
                }
            }
        ]
    };

    chart.setOption(option, true);
}
