import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
import time
import warnings
from datetime import datetime, timedelta, timezone
warnings.filterwarnings('ignore')

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8832925625:AAH40Jt4Ux2zDZXKA7cUW-LQtl6NtvcOhHY')
CHAT_ID = os.environ.get('CHAT_ID', '208377256')

STOCKS = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'NFLX', 'SPY']
ALL_US_STOCKS = ['AAPL','MSFT','GOOGL','GOOG','AMZN','META','NVDA','AMD','INTC','CSCO','ADBE','CRM','ORCL','IBM','QCOM','TXN','AVGO','NOW','INTU','AMAT','TSLA','F','GM','RIVN','LCID','NIO','XPEV','LI','NFLX','DIS','CMCSA','PARA','WBD','SPOT','ROKU','SHOP','SQ','PYPL','UBER','LYFT','DASH','ABNB','BKNG','JNJ','PFE','MRNA','BNTX','ABBV','UNH','LLY','MRK','JPM','BAC','WFC','GS','MS','V','MA','AXP','COF','WMT','TGT','COST','HD','LOW','NKE','SBUX','MCD','KO','PEP','BA','CAT','GE','HON','UPS','FDX','DAL','UAL','AAL','LUV','SPY','QQQ','IWM','DIA','VTI','VOO','XLF','XLE','XLK','XLV']

STOCK_NAMES = {'AAPL':'Apple','TSLA':'Tesla','MSFT':'Microsoft','GOOGL':'Alphabet','GOOG':'Alphabet C','AMZN':'Amazon','META':'Meta','NVDA':'NVIDIA','AMD':'AMD','INTC':'Intel','CSCO':'Cisco','ADBE':'Adobe','CRM':'Salesforce','ORCL':'Oracle','IBM':'IBM','QCOM':'Qualcomm','TXN':'Texas Instruments','AVGO':'Broadcom','NOW':'ServiceNow','INTU':'Intuit','AMAT':'Applied Materials','F':'Ford','GM':'General Motors','RIVN':'Rivian','LCID':'Lucid','NIO':'NIO','XPEV':'XPeng','LI':'Li Auto','NFLX':'Netflix','DIS':'Disney','CMCSA':'Comcast','PARA':'Paramount','WBD':'Warner Bros','SPOT':'Spotify','ROKU':'Roku','SHOP':'Shopify','SQ':'Block','PYPL':'PayPal','UBER':'Uber','LYFT':'Lyft','DASH':'DoorDash','ABNB':'Airbnb','BKNG':'Booking','JNJ':'Johnson & Johnson','PFE':'Pfizer','MRNA':'Moderna','BNTX':'BioNTech','ABBV':'AbbVie','UNH':'UnitedHealth','LLY':'Eli Lilly','MRK':'Merck','JPM':'JPMorgan','BAC':'Bank of America','WFC':'Wells Fargo','GS':'Goldman Sachs','MS':'Morgan Stanley','V':'Visa','MA':'Mastercard','AXP':'American Express','COF':'Capital One','WMT':'Walmart','TGT':'Target','COST':'Costco','HD':'Home Depot','LOW':"Lowe's",'NKE':'Nike','SBUX':'Starbucks','MCD':"McDonald's",'KO':'Coca-Cola','PEP':'PepsiCo','BA':'Boeing','CAT':'Caterpillar','GE':'General Electric','HON':'Honeywell','UPS':'UPS','FDX':'FedEx','DAL':'Delta','UAL':'United Airlines','AAL':'American Airlines','LUV':'Southwest','SPY':'S&P 500 ETF','QQQ':'Nasdaq 100 ETF','IWM':'Russell 2000 ETF','DIA':'Dow Jones ETF','VTI':'Total Market ETF','VOO':'S&P 500 Vanguard','XLF':'Financial ETF','XLE':'Energy ETF','XLK':'Tech ETF','XLV':'Healthcare ETF','^VIX':'VIX'}

PROCESSED_FILE = 'processed_messages.json'
LEARNING_FILE = 'learning_data.json'
SETTINGS_FILE = 'bot_settings.json'
NEWS_FILE = 'news_cache.json'

def load_json(fn, default=None):
    if default is None: default = {}
    try:
        with open(fn, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(fn, data):
    with open(fn, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)

def get_settings():
    defaults = {'capital': 10000, 'risk_percent': 2.0, 'rsi_threshold': 35, 'accuracy_score': 0, 'total_predictions': 0, 'correct_predictions': 0, 'last_adjustment': None, 'last_fast_learning': None, 'mistake_patterns': {'high_rsi': 0, 'low_volume': 0, 'weak_trend': 0, 'wrong_macd': 0}}
    settings = load_json(SETTINGS_FILE, defaults)
    for key in defaults:
        if key not in settings: settings[key] = defaults[key]
    return settings

def send_telegram(msg, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode}, timeout=10)
        return True
    except: return False

# ============================================
# 🔑 الحصول على Bot ID (الحل الحقيقي!)
# ============================================
def get_bot_id():
    """الحصول على ID البوت لتجاهل رسائله"""
    cache = load_json('bot_id_cache.json', {'bot_id': None, 'date': ''})
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if cache.get('bot_id') and cache.get('date') == today:
        return cache['bot_id']
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        response = requests.get(url, timeout=5).json()
        if response.get('ok'):
            bot_id = response['result']['id']
            save_json('bot_id_cache.json', {'bot_id': bot_id, 'date': today})
            print(f" Bot ID: {bot_id}")
            return bot_id
    except: pass
    return None

def get_last_processed_id():
    data = load_json(PROCESSED_FILE, {'last_id': 0, 'date': ''})
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if data.get('date') != today:
        data = {'last_id': 0, 'date': today}
        save_json(PROCESSED_FILE, data)
    return data.get('last_id', 0)

def save_last_processed_id(update_id):
    data = load_json(PROCESSED_FILE, {'last_id': 0, 'date': ''})
    data['last_id'] = update_id
    data['date'] = datetime.utcnow().strftime('%Y-%m-%d')
    save_json(PROCESSED_FILE, data)
    print(f"✅ حفظ last_id: {update_id}")

def get_current_time():
    utc_now = datetime.now(timezone.utc)
    saudi_tz = timezone(timedelta(hours=3))
    saudi_now = utc_now.astimezone(saudi_tz)
    return {
        'saudi': saudi_now.strftime('%Y-%m-%d %H:%M:%S (توقيت السعودية)'),
        'saudi_short': saudi_now.strftime('%H:%M'),
        'date': saudi_now.strftime('%Y-%m-%d')
    }

def get_vix():
    try:
        vix = yf.Ticker('^VIX')
        data = vix.history(period='5d')
        if len(data) > 0:
            current = float(data['Close'].iloc[-1])
            if current < 15: return {'value': round(current, 2), 'level': 'منخفض', 'emoji': '🟢'}
            elif current < 20: return {'value': round(current, 2), 'level': 'معتدل', 'emoji': '🟡'}
            elif current < 30: return {'value': round(current, 2), 'level': 'مرتفع', 'emoji': ''}
            else: return {'value': round(current, 2), 'level': 'مرتفع جداً', 'emoji': '🔴'}
    except: pass
    return None

def get_market_overview():
    try:
        spy = yf.Ticker('SPY')
        data = spy.history(period='5d')
        if len(data) > 0:
            current = float(data['Close'].iloc[-1])
            prev = float(data['Close'].iloc[-2])
            return {'price': round(current, 2), 'change': round(((current - prev) / prev) * 100, 2)}
    except: pass
    return None

def fast_learning():
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    if not learning_data.get('predictions'): return
    now = datetime.utcnow()
    last_fast = settings.get('last_fast_learning')
    if last_fast:
        try:
            if (now - datetime.fromisoformat(last_fast)).total_seconds() < 3600: return
        except: pass
    six_hours_ago = (now - timedelta(hours=6)).strftime('%Y-%m-%d %H')
    recent = [p for p in learning_data['predictions'] if p.get('timestamp', '') >= six_hours_ago]
    if not recent:
        settings['last_fast_learning'] = now.isoformat()
        save_json(SETTINGS_FILE, settings)
        return
    correct, wrong = 0, 0
    mistakes = {'high_rsi': 0, 'low_volume': 0, 'weak_trend': 0, 'wrong_macd': 0}
    for pred in recent:
        try:
            ticker = yf.Ticker(pred['symbol'])
            data = ticker.history(period='1d', interval='1h')
            if len(data) < 2: continue
            actual = float(data['Close'].iloc[-1])
            change = ((actual - pred['price']) / pred['price']) * 100
            if pred['action'] == 'buy':
                if change > 0.5: correct += 1
                else:
                    wrong += 1
                    if pred.get('rsi', 50) > 40: mistakes['high_rsi'] += 1
                    if pred.get('volume_ratio', 1) < 1.2: mistakes['low_volume'] += 1
                    if pred.get('adx', 0) < 25: mistakes['weak_trend'] += 1
                    if pred.get('macd', 0) < 0: mistakes['wrong_macd'] += 1
            else:
                if change < -0.5: correct += 1
                else: wrong += 1
        except: continue
    total = correct + wrong
    if total > 0:
        settings['total_predictions'] += total
        settings['correct_predictions'] += correct
        settings['accuracy_score'] = round(settings['correct_predictions'] / settings['total_predictions'], 2)
        for k in mistakes: settings['mistake_patterns'][k] += mistakes[k]
        rsi = settings['rsi_threshold']
        if mistakes['high_rsi'] > max(mistakes.get('low_volume', 0), mistakes.get('weak_trend', 0)) and rsi > 25:
            settings['rsi_threshold'] = max(25, rsi - 2)
            send_telegram(f"🧠 تعلم سريع: {mistakes['high_rsi']} أخطاء RSI. RSI: {rsi}→{settings['rsi_threshold']}. الدقة: {settings['accuracy_score']*100}%")
        elif mistakes['low_volume'] > 2:
            send_telegram(f"⚠️ {mistakes['low_volume']} أخطاء حجم منخفض")
        elif mistakes['weak_trend'] > 2:
            send_telegram(f"💪 {mistakes['weak_trend']} أخطاء اتجاه ضعيف")
        settings['last_fast_learning'] = now.isoformat()
        save_json(SETTINGS_FILE, settings)

def get_daily_news():
    news_cache = load_json(NEWS_FILE, {'last_update': None, 'news': []})
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if news_cache.get('last_update') == today: return news_cache['news']
    items = []
    for sym in ['SPY', 'AAPL', 'TSLA', 'MSFT', 'NVDA']:
        try:
            news = yf.Ticker(sym).news
            if news:
                for item in news[:3]:
                    t, p = item.get('title', ''), item.get('publisher', '')
                    if t and p:
                        items.append({'symbol': sym, 'title': t, 'publisher': p, 'time': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%H:%M')})
        except: continue
    save_json(NEWS_FILE, {'last_update': today, 'news': items[:15]})
    return items[:15]

def send_daily_news_report():
    news = get_daily_news()
    if not news: return
    time_info = get_current_time()
    vix = get_vix()
    msg = f"📰 <b>تقرير الأخبار اليومي</b>\n📅 {time_info['saudi']}\n\n"
    if vix: msg += f"😱 VIX: {vix['emoji']} {vix['value']} - {vix['level']}\n\n"
    by_sym = {}
    for item in news:
        by_sym.setdefault(item['symbol'], []).append(item)
    for sym, items in by_sym.items():
        msg += f"📌 <b>{STOCK_NAMES.get(sym, sym)} ({sym}):</b>\n"
        for item in items[:2]: msg += f"• {item['title']}\n  📰 {item['publisher']} | ⏰ {item['time']}\n\n"
    send_telegram(msg)

def analyze_best_times(symbol):
    try:
        data = yf.download(symbol, period='3mo', interval='30m', progress=False)
        if len(data) < 100: return None
        data['hour'] = data.index.hour
        data['return'] = data['Close'].pct_change() * 100
        return [(int(h), round(float(v), 2)) for h, v in data.groupby('hour')['return'].mean().nlargest(3).items()]
    except: return None

def analyze_best_days(symbol):
    try:
        data = yf.download(symbol, period='6mo', interval='1d', progress=False)
        if len(data) < 100: return None
        data['day_of_week'] = data.index.dayofweek
        data['return'] = data['Close'].pct_change() * 100
        days = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة'}
        return [(days.get(int(d), d), round(float(v), 2)) for d, v in data.groupby('day_of_week')['return'].mean().nlargest(3).items()]
    except: return None

def calculate_obv(data):
    try:
        obv = (np.sign(data['Close'].diff()) * data['Volume']).fillna(0).cumsum()
        return float(obv.iloc[-1]) > float(obv.rolling(20).mean().iloc[-1])
    except: return False

def calculate_adx(data, period=14):
    try:
        h, l, c = data['High'], data['Low'], data['Close']
        pdm = h.diff(); pdm[pdm < 0] = 0
        ndm = l.diff(); ndm[ndm > 0] = 0
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        pdi = 100 * (pdm.rolling(period).mean() / atr)
        ndi = 100 * (ndm.rolling(period).mean() / atr)
        dx = 100 * ((pdi - ndi).abs() / (pdi + ndi))
        adx = dx.rolling(period).mean()
        return float(adx.iloc[-1]) if not adx.empty else 0
    except: return 0

def detect_patterns(data):
    patterns = []
    try:
        if len(data) < 3: return patterns
        o, c, h, l = data['Open'].iloc[-1], data['Close'].iloc[-1], data['High'].iloc[-1], data['Low'].iloc[-1]
        body = abs(c - o)
        if min(o, c) - l > body * 2 and h - max(o, c) < body * 0.5 and c > o: patterns.append("🔨 مطرقة")
        if c > o and data['Close'].iloc[-2] < data['Open'].iloc[-2] and c > data['Open'].iloc[-2] and o < data['Close'].iloc[-2]: patterns.append("📈 ابتلاعية")
        if body < (h - l) * 0.1: patterns.append("⚖️ دوجي")
    except: pass
    return patterns

def explain_recommendation(result):
    score = result['score']
    exp = []
    if score >= 6: exp.append("🌟 <b>صفقة قوية جداً:</b> إشارات متعددة!")
    elif score >= 5: exp.append("✅ <b>شراء قوي:</b> معظم المؤشرات إيجابية.")
    elif score >= 4: exp.append("🟡 <b>شراء:</b> مؤشرات إيجابية.")
    elif score >= 3: exp.append("👀 <b>مراقبة:</b> يحتاج تأكيد.")
    else: exp.append("🔴 <b>تجنب:</b> مؤشرات سلبية.")
    exp.append("\n📝 <b>التفصيل:</b>")
    for r in result['reasons']:
        if 'RSI منخفض جداً' in r: exp.append(f"• {r} → مباع بشكل زائد")
        elif 'RSI منخفض' in r: exp.append(f"• {r} → اقتراب من الشراء")
        elif 'فوق المتوسط' in r: exp.append(f"• {r} → اتجاه صعودي")
        elif 'تحت المتوسط' in r: exp.append(f"• {r} → اتجاه هبوطي")
        elif 'MACD' in r: exp.append(f"• {r} → زخم صعودي")
        elif 'حجم' in r: exp.append(f"• {r} → اهتمام كبير")
        elif 'ADX' in r: exp.append(f"• {r} → اتجاه قوي")
        elif 'OBV' in r: exp.append(f"• {r} → تراكم مؤسساتي")
        else: exp.append(f"• {r}")
    return "\n".join(exp)

def learn_from_predictions():
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    if not learning_data.get('predictions'): return
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    preds = [p for p in learning_data['predictions'] if p.get('date') == yesterday]
    if not preds: return
    correct, wrong = 0, 0
    for pred in preds:
        try:
            data = yf.Ticker(pred['symbol']).history(period='2d', interval='1d')
            if len(data) < 2: continue
            change = ((float(data['Close'].iloc[-1]) - pred['price']) / pred['price']) * 100
            if (pred['action'] == 'buy' and change > 0) or (pred['action'] != 'buy' and change < 0): correct += 1
            else: wrong += 1
        except: continue
    total = correct + wrong
    if total > 0:
        settings['total_predictions'] += total
        settings['correct_predictions'] += correct
        settings['accuracy_score'] = round(settings['correct_predictions'] / settings['total_predictions'], 2)
        rsi = settings['rsi_threshold']
        if settings['accuracy_score'] < 0.45 and rsi > 25:
            settings['rsi_threshold'] = max(25, rsi - 3)
            send_telegram(f"🧠 تحسين! الدقة: {settings['accuracy_score']*100}%. RSI: {rsi}→{settings['rsi_threshold']}")
        elif settings['accuracy_score'] > 0.70 and rsi < 45:
            settings['rsi_threshold'] = min(45, rsi + 2)
            send_telegram(f"📈 تحسين! الدقة: {settings['accuracy_score']*100}%. RSI: {rsi}→{settings['rsi_threshold']}")
        settings['last_adjustment'] = yesterday
        save_json(SETTINGS_FILE, settings)
        learning_data['predictions'] = [p for p in learning_data['predictions'] if p.get('date') >= (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')]
        save_json(LEARNING_FILE, learning_data)

def analyze_stock(symbol, settings):
    try:
        data = yf.Ticker(symbol).history(period='6mo', interval='1d')
        if len(data) < 50: return None
        price = float(data['Close'].iloc[-1])
        prev = float(data['Close'].iloc[-2])
        change = ((price - prev) / prev) * 100
        sma = float(data['Close'].rolling(50).mean().iloc[-1])
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = float(100 - (100 / (1 + (gain / loss).iloc[-1])))
        macd = float(data['Close'].ewm(span=12, adjust=False).mean().iloc[-1] - data['Close'].ewm(span=26, adjust=False).mean().iloc[-1])
        vol = float(data['Volume'].iloc[-1])
        avg_vol = float(data['Volume'].rolling(20).mean().iloc[-1])
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1
        adx = calculate_adx(data)
        obv = calculate_obv(data)
        patterns = detect_patterns(data)
        tr = pd.concat([data['High'] - data['Low'], (data['High'] - data['Close'].shift(1)).abs(), (data['Low'] - data['Close'].shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        sl = round(price - (atr * 1.5), 2)
        t1 = round(price + (atr * 2), 2)
        t2 = round(price + (atr * 3), 2)
        risk_amt = settings['capital'] * settings['risk_percent'] / 100
        pos_size = int(risk_amt / (price - sl)) if price > sl and sl > 0 else 0
        score, reasons = 0, []
        rsi_th = settings.get('rsi_threshold', 35)
        if rsi < rsi_th: score += 2; reasons.append(f"📉 RSI منخفض جداً ({rsi:.1f})")
        elif rsi < rsi_th + 10: score += 1; reasons.append(f" RSI منخفض ({rsi:.1f})")
        if price > sma: score += 1; reasons.append("📈 السعر فوق المتوسط")
        else: reasons.append("📉 السعر تحت المتوسط")
        if macd > 0: score += 1; reasons.append("✅ MACD إيجابي")
        if vol_ratio > 1.5: score += 1; reasons.append(f"💪 حجم عالي ({vol_ratio:.1f}x)")
        if adx > 25: score += 1; reasons.append(f"💪 ADX قوي ({adx:.1f})")
        if obv: score += 1; reasons.append("🏦 تراكم OBV")
        if patterns: score += len(patterns); reasons.extend(patterns)
        if score >= 6: rec, conf = "🚨 صفقة قوية جداً", "عالية جداً"
        elif score >= 5: rec, conf = "✅ شراء قوي", "عالية"
        elif score >= 4: rec, conf = "🟡 شراء", "متوسطة"
        elif score >= 3: rec, conf = "👀 مراقبة", "منخفضة"
        else: rec, conf = " تجنب", "ضعيفة"
        rr = round((t1 - price) / (price - sl), 2) if sl > 0 else 0
        return {'symbol': symbol, 'price': price, 'change': round(change, 2), 'rsi': round(rsi, 1), 'macd': round(macd, 2), 'adx': round(adx, 1), 'volume_ratio': round(vol_ratio, 2), 'score': score, 'recommendation': rec, 'confidence': conf, 'reasons': reasons, 'stop_loss': sl, 'target1': t1, 'target2': t2, 'pos_size': pos_size, 'total_inv': round(pos_size * price, 2), 'risk_amt': round(risk_amt, 2), 'best_times': analyze_best_times(symbol), 'best_days': analyze_best_days(symbol), 'risk_reward': rr, 'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H')}
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

def find_affordable_stocks(settings, max_results=10):
    capital = settings['capital']
    risk_amt = capital * settings['risk_percent'] / 100
    affordable = []
    for sym in ALL_US_STOCKS[:30]:
        try:
            data = yf.Ticker(sym).history(period='5d', interval='1d')
            if len(data) < 3: continue
            price = float(data['Close'].iloc[-1])
            pos = min(int(capital / price), int(risk_amt / (price * 0.02)))
            if pos >= 10:
                delta = data['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = float(100 - (100 / (1 + (gain / loss).iloc[-1]))) if len(gain) > 0 else 50
                affordable.append({'symbol': sym, 'name': STOCK_NAMES.get(sym, sym), 'price': price, 'change': round(((price - float(data['Close'].iloc[-2])) / float(data['Close'].iloc[-2])) * 100, 2), 'rsi': round(rsi, 1), 'position_size': pos, 'total_investment': round(pos * price, 2)})
        except: continue
    affordable.sort(key=lambda x: x['price'])
    return affordable[:max_results]

def handle_chat(text):
    text_lower = text.lower().strip()
    settings = get_settings()
    for stock in STOCKS + ALL_US_STOCKS:
        if stock.lower() in text_lower or stock in text_lower:
            result = analyze_stock(stock, settings)
            if result:
                name = STOCK_NAMES.get(stock, stock)
                msg = f"📊 <b>تحليل {name} ({stock}):</b>\n\n💰 السعر: ${result['price']} ({result['change']:+.2f}%)\n RSI: {result['rsi']} | MACD: {result['macd']} | ADX: {result['adx']}\n🎯 {result['recommendation']} ({result['confidence']})\n⭐ النقاط: {result['score']}/8\n\n"
                msg += explain_recommendation(result) + "\n\n"
                msg += f"<b>💰 الخطة:</b>\n• العدد: {result['pos_size']} سهم\n• الاستثمار: ${result['total_inv']}\n• المخاطرة: ${result['risk_amt']}\n🛡️ SL: ${result['stop_loss']}\n T1: ${result['target1']}\n🎯 T2: ${result['target2']}\n⚖️ R/R: {result['risk_reward']}:1\n"
                if result.get('best_times'): msg += f"\n أفضل وقت: {result['best_times'][0][0]}:00 (+{result['best_times'][0][1]}%)\n"
                if result.get('best_days'): msg += f"📅 أفضل يوم: {result['best_days'][0][0]} (+{result['best_days'][0][1]}%)\n"
                return msg
            return f"❌ لا بيانات لـ {stock}"
    if any(w in text_lower for w in ['اسهم رخيصة', 'رخيصة', 'cheap', 'affordable', 'ميزانيتي', 'budget']):
        affordable = find_affordable_stocks(settings)
        if affordable:
            msg = f"💰 <b>أسهم لميزانيتك (${settings['capital']}):</b>\n\n"
            for s in affordable: msg += f"📌 <b>{s['name']} ({s['symbol']})</b>\n💰 ${s['price']} ({s['change']:+.2f}%)\n RSI: {s['rsi']}\n🔢 {s['position_size']} سهم\n💵 ${s['total_investment']}\n\n"
            return msg
        return "❌ لا أسهم مناسبة"
    if any(w in text_lower for w in ['اخبار', 'news']):
        news = get_daily_news()
        if news:
            msg = "📰 <b>آخر الأخبار:</b>\n\n"
            for item in news[:5]: msg += f" <b>{STOCK_NAMES.get(item['symbol'], item['symbol'])}:</b> {item['title']}\n📰 {item['publisher']} | ⏰ {item['time']}\n\n"
            return msg
        return "📰 لا أخبار"
    if any(w in text_lower for w in ['vix', 'الخوف']):
        vix = get_vix()
        if vix: return f"😱 <b>VIX:</b> {vix['emoji']} {vix['value']} - {vix['level']}"
        return "❌ لا VIX"
    if any(w in text_lower for w in ['rsi', 'ما هو rsi']):
        return "📊 <b>RSI:</b>\n📉 <30: مباع زائد\n📈 >70: مشتري زائد\n⚖️ 30-70: محايد"
    if any(w in text_lower for w in ['مرحبا', 'هلا', 'hi', 'hello']):
        return "👋 أهلاً! 🤖 بوت تحليل الأسهم.\n\nجرب: TSLA, أسهم رخيصة, vix, /help"
    if any(w in text_lower for w in ['شكر', 'thanks']):
        return "😊 العفو!"
    if any(w in text_lower for w in ['دقة', 'accuracy']):
        return f"🎯 الدقة: {settings['accuracy_score']*100}%\n✅ {settings['correct_predictions']}/{settings['total_predictions']}\n⚙️ RSI: {settings['rsi_threshold']}"
    return "🤔 جرب: TSLA, أسهم رخيصة, vix, /help"

def process_message(text, settings):
    if text == '/settings':
        msg = f"️ <b>الإعدادات:</b>\n💰 ${settings['capital']}\n⚠️ {settings['risk_percent']}%\n🧠 RSI: {settings['rsi_threshold']}\n🎯 الدقة: {settings['accuracy_score']*100}%\n📊 {settings['total_predictions']} توقع\n✅ {settings['correct_predictions']} صحيح\n\n<b>الأخطاء:</b>\n• RSI: {settings['mistake_patterns'].get('high_rsi', 0)}\n• حجم: {settings['mistake_patterns'].get('low_volume', 0)}\n• اتجاه: {settings['mistake_patterns'].get('weak_trend', 0)}\n• MACD: {settings['mistake_patterns'].get('wrong_macd', 0)}"
        send_telegram(msg)
    elif text == '/help':
        send_telegram(" <b>الأوامر:</b>\n/settings\n/status\n/stock [رمز]\n/affordable\n/news\n/vix\n/learn\n\nاكتب: TSLA, أسهم رخيصة, vix")
    elif text == '/vix':
        vix = get_vix()
        if vix: send_telegram(f"😱 <b>VIX:</b> {vix['emoji']} {vix['value']} - {vix['level']}")
    elif text == '/learn':
        learn_from_predictions()
        send_telegram("✅ تمت المراجعة!")
    elif text == '/news':
        send_telegram("⏳ جاري...")
        send_daily_news_report()
    elif text.startswith('/stock '):
        sym = text.split()[1].upper()
        result = analyze_stock(sym, settings)
        if result:
            name = STOCK_NAMES.get(result['symbol'], result['symbol'])
            msg = f"📊 <b>{name} ({result['symbol']}):</b>\n💰 ${result['price']} ({result['change']:+.2f}%)\n📈 RSI: {result['rsi']} | MACD: {result['macd']} | ADX: {result['adx']}\n🎯 {result['recommendation']} ({result['confidence']})\n⭐ {result['score']}/8\n\n"
            msg += explain_recommendation(result) + "\n\n"
            msg += f"<b>💰 الخطة:</b>\n• {result['pos_size']} سهم\n• ${result['total_inv']}\n• مخاطرة: ${result['risk_amt']}\n️ SL: ${result['stop_loss']}\n🎯 T1: ${result['target1']}\n🎯 T2: ${result['target2']}\n⚖️ R/R: {result['risk_reward']}:1\n"
            if result.get('best_times'): msg += f"\n⏰ {result['best_times'][0][0]}:00 (+{result['best_times'][0][1]}%)\n"
            if result.get('best_days'): msg += f"📅 {result['best_days'][0][0]} (+{result['best_days'][0][1]}%)\n"
            send_telegram(msg)
        else: send_telegram(f"❌ لا بيانات لـ {sym}")
    elif text == '/affordable':
        send_telegram("⏳ جاري...")
        affordable = find_affordable_stocks(settings)
        if affordable:
            msg = f"💰 <b>أسهم لميزانيتك (${settings['capital']}):</b>\n\n"
            for s in affordable: msg += f"📌 <b>{s['name']} ({s['symbol']})</b>\n💰 ${s['price']} ({s['change']:+.2f}%)\n RSI: {s['rsi']}\n🔢 {s['position_size']} سهم\n ${s['total_investment']}\n\n"
            send_telegram(msg)
        else: send_telegram("❌ لا أسهم")
    elif text == '/status':
        today = datetime.utcnow().strftime('%Y-%m-%d')
        preds = len([p for p in load_json(LEARNING_FILE, {'predictions': []}).get('predictions', []) if p.get('date') == today])
        send_telegram(f"🧠 <b>الحالة:</b>\n🎯 الدقة: {settings['accuracy_score']*100}%\n⚙️ RSI: {settings['rsi_threshold']}\n📝 اليوم: {preds}\n يتعلم كل ساعة!")
    elif text and not text.startswith('/'):
        resp = handle_chat(text)
        if resp: send_telegram(resp)

# ============================================
# 🔑 handle_commands - الحل النهائي المضمون
# ============================================
def handle_commands():
    print("💬 بدء معالجة الأوامر...")
    
    # 1. الحصول على Bot ID
    bot_id = get_bot_id()
    print(f"🤖 Bot ID: {bot_id}")
    
    # 2. قراءة آخر update_id
    last_id = get_last_processed_id()
    print(f"📋 آخر ID: {last_id}")
    
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
    try:
        # 3. الحصول على التحديثات
        url = f"{url_base}/getUpdates?offset={last_id + 1}&limit=100&timeout=5"
        print(f"📡 الاتصال...")
        response = requests.get(url, timeout=10).json()
        
        if not response.get('ok'):
            print("❌ فشل الاتصال")
            return
        
        updates = response.get('result', [])
        print(f"📨 عدد التحديثات: {len(updates)}")
        
        if not updates:
            print("📭 لا تحديثات")
            return
        
        settings = get_settings()
        processed = 0
        skipped_bot = 0
        skipped_other = 0
        max_id = last_id
        
        for update in updates:
            update_id = update['update_id']
            if update_id > max_id:
                max_id = update_id
            
            message = update.get('message', {})
            if not message:
                continue
            
            # 🔑 التحقق من المرسل
            sender = message.get('from', {})
            sender_id = sender.get('id')
            is_bot = sender.get('is_bot', False)
            
            # تجاهل رسائل البوت نفسه
            if is_bot or sender_id == bot_id:
                print(f" تخطي رسالة من البوت (ID: {update_id})")
                skipped_bot += 1
                continue
            
            text = message.get('text', '').strip()
            chat_id = str(message.get('chat', {}).get('id', ''))
            
            print(f"💬 رسالة من {chat_id}: {text[:50]}")
            
            if chat_id != CHAT_ID:
                print(f"⚠️ Chat ID غير مطابق")
                skipped_other += 1
                continue
            
            try:
                process_message(text, settings)
                processed += 1
                print(f"✅ تمت المعالجة: {update_id}")
            except Exception as e:
                print(f"❌ خطأ: {e}")
        
        # 4. حفظ آخر ID
        save_last_processed_id(max_id)
        print(f"✅ تمت معالجة {processed}، تخطي {skipped_bot} بوت، {skipped_other} أخرى")
        print(f"✅ آخر ID: {max_id}")
    
    except Exception as e:
        print(f"❌ خطأ: {e}")

def run_scan():
    print("🎯 بدء فحص السوق...")
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    time_info = get_current_time()
    vix = get_vix()
    market = get_market_overview()
    today = time_info['date']
    results, strong = [], []
    
    for sym in settings.get('stocks', STOCKS):
        try:
            result = analyze_stock(sym, settings)
            if result:
                results.append(result)
                learning_data['predictions'].append({'symbol': sym, 'price': result['price'], 'action': 'buy' if result['score'] >= 3 else 'avoid', 'rsi': result['rsi'], 'score': result['score'], 'volume_ratio': result.get('volume_ratio', 1), 'adx': result.get('adx', 0), 'macd': result.get('macd', 0), 'date': today, 'time': time_info['saudi_short'], 'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H')})
                if result['score'] >= 5: strong.append(result)
        except Exception as e: print(f"خطأ {sym}: {e}")
    
    save_json(LEARNING_FILE, learning_data)
    
    if results:
        results.sort(key=lambda x: x['score'], reverse=True)
        msg = f"📊 <b>فحص السوق</b>\n {time_info['saudi']}\n الدقة: {settings['accuracy_score']*100}% | RSI: {settings['rsi_threshold']}\n\n"
        if vix: msg += f"😱 VIX: {vix['emoji']} {vix['value']} - {vix['level']}\n"
        if market: msg += f"📈 S&P: ${market['price']} ({market['change']:+.2f}%)\n"
        msg += f"\n<b>🏆 أفضل 3:</b>\n\n"
        for r in results[:3]:
            name = STOCK_NAMES.get(r['symbol'], r['symbol'])
            msg += f"📌 <b>{name} ({r['symbol']})</b> ({r['change']:+.2f}%)\n💰 ${r['price']} | RSI: {r['rsi']} | ADX: {r['adx']}\n{r['recommendation']} ({r['score']} نقاط)\n📝 {', '.join(r['reasons'])}\n🛡️ SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n⚖️ R/R: {r['risk_reward']}:1\n\n"
            msg += explain_recommendation(r) + "\n\n"
            if r.get('best_times'): msg += f"⏰ {r['best_times'][0][0]}:00 (+{r['best_times'][0][1]}%)\n"
            if r.get('best_days'): msg += f"📅 {r['best_days'][0][0]} (+{r['best_days'][0][1]}%)\n\n"
        if strong:
            msg += f"\n🚨 <b>فرص قوية!</b>\n\n"
            for r in strong:
                name = STOCK_NAMES.get(r['symbol'], r['symbol'])
                msg += f"🔥 <b>{name} ({r['symbol']})</b> - {r['recommendation']}\n💰 ${r['price']} | RSI: {r['rsi']}\n⭐ {r['score']}/8\n🛡️ SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n⚖️ R/R: {r['risk_reward']}:1\n\n"
                msg += explain_recommendation(r) + "\n\n"
                if r.get('best_times'): msg += f"⏰ {r['best_times'][0][0]}:00\n"
                if r.get('best_days'): msg += f" {r['best_days'][0][0]}\n"
                msg += f"💰 {r['pos_size']} سهم (${r['total_inv']})\n\n"
        send_telegram(msg)
        print(f"✅ تم إرسال التقرير ({len(strong)} فرصة قوية)")
    else: print("لا توجد بيانات")
    print("✅ انتهى الفحص")

if __name__ == '__main__':
    print("🚀 بدء البوت...")
    print("1️⃣ الأوامر...")
    handle_commands()
    now = datetime.utcnow()
    print("2️⃣ التعلم...")
    fast_learning()
    if now.hour == 10:
        print("3️ مراجعة يومية...")
        learn_from_predictions()
    if now.hour == 9 and now.minute < 10:
        print("4️ أخبار...")
        send_daily_news_report()
    print("5️⃣ فحص...")
    run_scan()
    print("✅ انتهى")
