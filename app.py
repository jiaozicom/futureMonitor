from flask import Flask, render_template, jsonify, request
import requests
import json
import time
from datetime import datetime, timezone

app = Flask(__name__)

# 商品配置
COMMODITIES = {
    'gold': {'symbol': 'GC=F', 'name': '黄金', 'color': '#FFD700'},
    'oil': {'symbol': 'CL=F', 'name': '原油', 'color': '#8B4513'},
    'dxy': {'symbol': 'DX-Y.NYB', 'name': '美元指数', 'color': '#228B22'},
    'vix': {'symbol': '^VIX', 'name': 'VIX恐慌指数', 'color': '#DC143C'},
}

# 周期配置
INTERVALS = {
    '1h': {'interval': '1h', 'range': '30d'},
    '4h': {'interval': '1h', 'range': '60d'},   # 用1h聚合为4h
    '1d': {'interval': '1d', 'range': '1y'},
}

YAHOO_API_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def fetch_yahoo_data(symbol, interval, data_range):
    """直接调用Yahoo Finance API获取数据"""
    params = {
        'interval': interval,
        'range': data_range,
        'includePrePost': 'false',
        'events': '',
    }

    url = YAHOO_API_URL.format(symbol=symbol)
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = data.get('chart', {}).get('result', [])
    if not result:
        return None

    chart_data = result[0]
    timestamps = chart_data.get('timestamp', [])
    quote = chart_data['indicators']['quote'][0]

    opens = quote.get('open', [])
    highs = quote.get('high', [])
    lows = quote.get('low', [])
    closes = quote.get('close', [])
    volumes = quote.get('volume', [])

    rows = []
    for i in range(len(timestamps)):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        v = volumes[i] if i < len(volumes) else None

        if o is None or h is None or l is None or c is None:
            continue

        rows.append({
            'ts': timestamps[i],
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': v or 0
        })

    return rows


def aggregate_4h(rows):
    """将1h数据聚合为4h K线"""
    if not rows:
        return []

    buckets = {}
    for r in rows:
        # 按4小时分桶
        bucket_ts = (r['ts'] // (4 * 3600)) * (4 * 3600)
        if bucket_ts not in buckets:
            buckets[bucket_ts] = {
                'ts': bucket_ts,
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
                'volume': r['volume']
            }
        else:
            b = buckets[bucket_ts]
            b['high'] = max(b['high'], r['high'])
            b['low'] = min(b['low'], r['low'])
            b['close'] = r['close']
            b['volume'] += r['volume']

    return sorted(buckets.values(), key=lambda x: x['ts'])


def format_rows(rows, is_daily=False):
    """格式化为前端需要的数据"""
    dates = []
    values = []
    volumes = []

    for r in rows:
        dt = datetime.fromtimestamp(r['ts'], tz=timezone.utc)
        if is_daily:
            date_str = dt.strftime('%Y-%m-%d')
        else:
            date_str = dt.strftime('%Y-%m-%d %H:%M')

        dates.append(date_str)
        values.append([
            round(r['open'], 2),
            round(r['close'], 2),
            round(r['low'], 2),
            round(r['high'], 2)
        ])
        volumes.append(int(r['volume']))

    return dates, values, volumes


@app.route('/')
def index():
    return render_template('index.html', commodities=COMMODITIES)


@app.route('/api/prices')
def get_prices():
    """获取所有商品的当前价格"""
    prices = {}
    for key, config in COMMODITIES.items():
        try:
            url = YAHOO_API_URL.format(symbol=config['symbol'])
            params = {'interval': '1d', 'range': '1d', 'includePrePost': 'false'}
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            result = data.get('chart', {}).get('result', [])
            if result:
                meta = result[0].get('meta', {})
                price = meta.get('regularMarketPrice', 0)
                prev_close = meta.get('chartPreviousClose', meta.get('previousClose', 0))
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0
                prices[key] = {
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'changePct': round(change_pct, 2),
                }
            else:
                prices[key] = {'price': 0, 'change': 0, 'changePct': 0}
        except Exception:
            prices[key] = {'price': 0, 'change': 0, 'changePct': 0}

    return jsonify(prices)


@app.route('/api/kline')
def get_kline():
    commodity = request.args.get('commodity', 'gold')
    interval = request.args.get('interval', '1d')

    if commodity not in COMMODITIES:
        return jsonify({'error': '未知商品'}), 400

    config = COMMODITIES[commodity]
    iv_config = INTERVALS.get(interval, INTERVALS['1d'])

    try:
        rows = fetch_yahoo_data(config['symbol'], iv_config['interval'], iv_config['range'])

        if not rows:
            return jsonify({'error': '无数据'}), 404

        # 4h需要聚合
        if interval == '4h':
            rows = aggregate_4h(rows)

        is_daily = (interval == '1d')
        dates, values, volumes = format_rows(rows, is_daily)

        return jsonify({
            'dates': dates,
            'values': values,
            'volumes': volumes,
            'name': config['name'],
            'color': config['color'],
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Yahoo API 请求失败: {str(e)}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
