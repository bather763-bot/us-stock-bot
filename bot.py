import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8832925625:AAH40Jt4Ux2zDZXKA7cUW-LQtl6NtvcOhHY')
CHAT_ID = os.environ.get('CHAT_ID', '208377256')

STOCKS = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'NFLX', 'SPY']
ALL_US_STOCKS = ['AAPL','MSFT','GOOGL','GOOG','AMZN','META','NVDA','AMD','INTC','CSCO','ADBE','CRM','ORCL','IBM','QCOM','TXN','AVGO','NOW','INTU','AMAT','TSLA','F','GM','RIVN','LCID','NIO','XPEV','LI','NFLX','DIS','CMCSA','PARA','WBD','SPOT','ROKU','SHOP','SQ','PYPL','UBER','LYFT','DASH','ABNB','BKNG','JNJ','PFE','MRNA','BNTX','ABBV','UNH','LLY','MRK','JPM','BAC','WFC','GS','MS','V','MA','AXP','COF','WMT','TGT','COST','HD','LOW','NKE','SBUX','MCD','KO','PEP','BA','CAT','GE','HON','UPS','FDX','DAL','UAL','AAL','LUV','SPY','QQQ','IWM','DIA','VTI','VOO','XLF','XLE','XLK','XLV']

STOCK_NAMES = {'AAPL':'Apple','TSLA':'Tesla','MSFT':'Microsoft','GOOGL':'Alphabet (Google)','GOOG':'Alphabet Class C','AMZN':'Amazon','META':'Meta (Facebook)','NVDA':'NVIDIA','AMD':'AMD','INTC':'Intel','CSCO':'Cisco','ADBE':'Adobe','CRM':'Salesforce','ORCL':'Oracle','IBM':'IBM','QCOM':'Qualcomm','TXN':'Texas Instruments','AVGO':'Broadcom','NOW':'ServiceNow','INTU':'Intuit','AMAT':'Applied Materials','F':'Ford','GM':'General Motors','RIVN':'Rivian','LCID':'Lucid','NIO':'NIO','XPEV':'XPeng','LI':'Li Auto','NFLX':'Netflix','DIS':'Disney','CMCSA':'Comcast','PARA':'Paramount','WBD':'Warner Bros','SPOT':'Spotify','ROKU':'Roku','SHOP':'Shopify','SQ':'Block','PYPL':'PayPal','UBER':'Uber','LYFT':'Lyft','DASH':'DoorDash','ABNB':'Airbnb','BKNG':'Booking','JNJ':'Johnson & Johnson','PFE':'Pfizer','MRNA':'Moderna','BNTX':'BioNTech','ABBV':'AbbVie','UNH':'UnitedHealth','LLY':'Eli Lilly','MRK':'Merck','JPM':'JPMorgan','BAC':'Bank of America','WFC':'Wells Fargo','GS':'Goldman Sachs','MS':'Morgan Stanley','V':'Visa','MA':'Mastercard','AXP':'American Express','COF':'Capital One','WMT':'Walmart','TGT':'Target','COST':'Costco','HD':'Home Depot','LOW':"Lowe's",'NKE':'Nike','SBUX':'Starbucks','MCD':"McDonald's",'KO':'Coca-Cola','PEP':'PepsiCo','BA':'Boeing','CAT':'Caterpillar','GE':'General Electric','HON':'Honeywell','UPS':'UPS','FDX':'FedEx','DAL':'Delta','UAL':'United Airlines','AAL':'American Airlines','LUV':'Southwest','SPY':'S&P 500 ETF','QQQ':'Nasdaq 100 ETF','IWM':'Russell 2000 ETF','DIA':'Dow Jones ETF','VTI':'Total Market ETF','VOO':'S&P 500 Vanguard','XLF':'Financial ETF','XLE':'Energy ETF','XLK':'Tech ETF','XLV':'Healthcare ETF'}

LEARNING_FILE = 'learning_data.json'
SETTINGS_FILE = 'bot_settings.json'
NEWS_FILE = 'news_cache.json'
UPDATE_FILE = 'last_update_id.json'

def load_json(fn, default=None):
    if default is None:
        default = {}
    try:
        with open(fn, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def save_json(fn, data):
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_settings():
    defaults = {
        'capital': 10000,
        'risk_percent': 2.0,
        'rsi_threshold': 35,
        'accuracy_score': 0,
        'total_predictions': 0,
        'correct_predictions': 0,
        'last_adjustment': None,
        'last_fast_learning': None,
        'mistake_patterns': {'high_rsi': 0, 'low_volume': 0, 'weak_trend': 0, 'wrong_macd': 0}
    }
    settings = load_json(SETTINGS_FILE, defaults)
    for key in defaults:
        if key not in settings:
            settings[key] = defaults[key]
    return settings

def send_telegram(msg, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode}, timeout=10)
        return True
    except Exception as e:
        print(f"خطأ تليجرام: {e}")
        return False

def get_last_update_id():
    data = load_json(UPDATE_FILE, {'last_update_id': 0})
    return data.get('last_update_id', 0)

def save_last_update_id(update_id):
    save_json(UPDATE_FILE, {'last_update_id': update_id})

def fast_learning():
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    if not learning_data.get('predictions'):
        return
    now = datetime.utcnow()
    last_fast = settings.get('last_fast_learning')
    if last_fast:
        try:
            last_time = datetime.fromisoformat(last_fast)
            if (now - last_time).total_seconds() < 3600:
                return
        except:
            pass
    print("تعلم سريع...")
    six_hours_ago = (now - timedelta(hours=6)).strftime('%Y-%m-%d %H')
    recent_preds = [p for p in learning_data['predictions'] if p.get('timestamp', '') >= six_hours_ago]
    if not recent_preds:
        settings['last_fast_learning'] = now.isoformat()
        save_json(SETTINGS_FILE, settings)
        return
    correct, wrong = 0, 0
    mistake_reasons = {'high_rsi': 0, 'low_volume': 0, 'weak_trend': 0, 'wrong_macd': 0}
    for pred in recent_preds:
        try:
            symbol = pred['symbol']
            predicted_price = pred['price']
            predicted_action = pred['action']
            pred_rsi = pred.get('rsi', 50)
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1h')
            if len(data) < 2:
                continue
            actual_price = float(data['Close'].iloc[-1])
            price_change = ((actual_price - predicted_price) / predicted_price) * 100
            if predicted_action == 'buy':
                if price_change > 0.5:
                    correct += 1
                else:
                    wrong += 1
                    if pred_rsi > 40:
                        mistake_reasons['high_rsi'] += 1
                    if pred.get('volume_ratio', 1) < 1.2:
                        mistake_reasons['low_volume'] += 1
                    if pred.get('adx', 0) < 25:
                        mistake_reasons['weak_trend'] += 1
                    if pred.get('macd', 0) < 0:
                        mistake_reasons['wrong_macd'] += 1
            else:
                if price_change < -0.5:
                    correct += 1
                else:
                    wrong += 1
        except:
            continue
    total = correct + wrong
    if total > 0:
        hourly_accuracy = correct / total
        settings['total_predictions'] += total
        settings['correct_predictions'] += correct
        settings['accuracy_score'] = round(settings['correct_predictions'] / settings['total_predictions'], 2)
        for key in mistake_reasons:
            settings['mistake_patterns'][key] += mistake_reasons[key]
        current_rsi = settings['rsi_threshold']
        if mistake_reasons['high_rsi'] > mistake_reasons.get('low_volume', 0) and mistake_reasons['high_rsi'] > mistake_reasons.get('weak_trend', 0):
            if current_rsi > 25:
                settings['rsi_threshold'] = max(25, current_rsi - 2)
                send_telegram(f"تعلم سريع: {mistake_reasons['high_rsi']} اخطاء بسبب RSI مرتفع. RSI: {current_rsi} -> {settings['rsi_threshold']}. الدقة: {settings['accuracy_score']*100}%")
        elif mistake_reasons['low_volume'] > 2:
            send_telegram(f"تنبيه: {mistake_reasons['low_volume']} اخطاء بسبب حجم تداول منخفض.")
        elif mistake_reasons['weak_trend'] > 2:
            send_telegram(f"تعلم: {mistake_reasons['weak_trend']} اخطاء بسبب اتجاه ضعيف.")
        settings['last_fast_learning'] = now.isoformat()
        save_json(SETTINGS_FILE, settings)
        print(f"الدقة {hourly_accuracy*100}%، RSI {settings['rsi_threshold']}")

def get_daily_news():
    print("اخبار السوق...")
    news_cache = load_json(NEWS_FILE, {'last_update': None, 'news': []})
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if news_cache.get('last_update') == today:
        return news_cache['news']
    news_items = []
    for symbol in ['SPY', 'AAPL', 'TSLA', 'MSFT', 'NVDA']:
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            if news:
                for item in news[:3]:
                    title = item.get('title', '')
                    publisher = item.get('publisher', '')
                    published = item.get('providerPublishTime', 0)
                    if title and publisher:
                        news_items.append({
                            'symbol': symbol,
                            'title': title,
                            'publisher': publisher,
                            'time': datetime.fromtimestamp(published).strftime('%H:%M') if published else ''
                        })
        except:
            continue
    news_cache = {'last_update': today, 'news': news_items[:15]}
    save_json(NEWS_FILE, news_cache)
    return news_items[:15]

def send_daily_news_report():
    news = get_daily_news()
    if not news:
        return
    msg = "تقرير الاخبار اليومي\n"
    msg += f"{datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
    by_symbol = {}
    for item in news:
        symbol = item['symbol']
        if symbol not in by_symbol:
            by_symbol[symbol] = []
        by_symbol[symbol].append(item)
    for symbol, items in by_symbol.items():
        stock_name = STOCK_NAMES.get(symbol, symbol)
        msg += f"{stock_name} ({symbol}):\n"
        for item in items[:2]:
            msg += f"- {item['title']}\n"
            msg += f"  {item['publisher']} | {item['time']}\n\n"
    msg += "نصيحة: تابع الاخبار لاتخاذ قرارات افضل!"
    send_telegram(msg)
    print("تم ارسال الاخبار")

def analyze_best_times(symbol):
    try:
        data = yf.download(symbol, period='3mo', interval='30m', progress=False)
        if len(data) < 100:
            return None
        data['hour'] = data.index.hour
        data['return'] = data['Close'].pct_change() * 100
        hourly_stats = data.groupby('hour')['return'].mean()
        best_times = hourly_stats.nlargest(3)
        return [(int(h), round(float(v), 2)) for h, v in best_times.items()]
    except:
        return None

def analyze_best_days(symbol):
    try:
        data = yf.download(symbol, period='6mo', interval='1d', progress=False)
        if len(data) < 100:
            return None
        data['day_of_week'] = data.index.dayofweek
        data['return'] = data['Close'].pct_change() * 100
        days_arabic = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الاربعاء', 3: 'الخميس', 4: 'الجمعة'}
        day_stats = data.groupby('day_of_week')['return'].mean()
        best_days = day_stats.nlargest(3)
        return [(days_arabic.get(int(d), d), round(float(v), 2)) for d, v in best_days.items()]
    except:
        return None

def calculate_obv(data):
    try:
        close = data['Close']
        volume = data['Volume']
        direction = np.sign(close.diff())
        obv = (direction * volume).fillna(0).cumsum()
        obv_sma = obv.rolling(window=20).mean()
        return float(obv.iloc[-1]) > float(obv_sma.iloc[-1])
    except:
        return False

def calculate_adx(data, period=14):
    try:
        high = data['High']
        low = data['Low']
        close = data['Close']
        plus_dm = high.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm = low.diff()
        minus_dm[minus_dm > 0] = 0
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(window=period).mean()
        return float(adx.iloc[-1]) if not adx.empty else 0
    except:
        return 0

def detect_patterns(data):
    patterns = []
    try:
        if len(data) < 3:
            return patterns
        open_p = data['Open'].iloc[-1]
        close_p = data['Close'].iloc[-1]
        high_p = data['High'].iloc[-1]
        low_p = data['Low'].iloc[-1]
        body = abs(close_p - open_p)
        upper_shadow = high_p - max(open_p, close_p)
        lower_shadow = min(open_p, close_p) - low_p
        prev_close = data['Close'].iloc[-2]
        prev_open = data['Open'].iloc[-2]
        if lower_shadow > body * 2 and upper_shadow < body * 0.5 and close_p > open_p:
            patterns.append("مطرقة (صعود)")
        if close_p > open_p and prev_close < prev_open and close_p > prev_open and open_p < prev_close:
            patterns.append("ابتلاعية صعودية")
        if body < (high_p - low_p) * 0.1:
            patterns.append("دوجي (تردد)")
    except:
        pass
    return patterns

def explain_recommendation(result):
    explanations = []
    score = result['score']
    if score >= 6:
        explanations.append("لماذا صفقة قوية جداً؟")
        explanations.append(f"حصل على {score}/8 نقاط - اشارات ايجابية متعددة!")
    elif score >= 5:
        explanations.append("لماذا شراء قوي؟")
        explanations.append(f"حصل على {score}/8 نقاط - معظم المؤشرات ايجابية.")
    elif score >= 4:
        explanations.append("لماذا شراء؟")
        explanations.append(f"حصل على {score}/8 نقاط - مؤشرات مختلطة لكن ايجابية.")
    elif score >= 3:
        explanations.append("لماذا مراقبة فقط؟")
        explanations.append(f"حصل على {score}/8 نقاط - يحتاج تاكيد اكثر.")
    else:
        explanations.append("لماذا تجنب؟")
        explanations.append(f"حصل على {score}/8 نقاط - المؤشرات سلبية.")
    explanations.append("\nتفصيل المؤشرات:")
    for reason in result['reasons']:
        if 'RSI منخفض جداً' in reason:
            explanations.append(f"- {reason} => السهم مباع بشكل زائد، قد يرتد صعوداً")
        elif 'RSI منخفض' in reason:
            explanations.append(f"- {reason} => اقتراب من منطقة الشراء")
        elif 'السعر فوق المتوسط' in reason:
            explanations.append(f"- {reason} => اتجاه صعودي عام")
        elif 'السعر تحت المتوسط' in reason:
            explanations.append(f"- {reason} => اتجاه هبوطي عام")
        elif 'MACD ايجابي' in reason:
            explanations.append(f"- {reason} => زخم صعودي قوي")
        elif 'حجم تداول عالي' in reason:
            explanations.append(f"- {reason} => اهتمام كبير من المستثمرين")
        elif 'اتجاه قوي' in reason:
            explanations.append(f"- {reason} => اتجاه واضح وقوي")
        elif 'تراكم مؤسساتي' in reason:
            explanations.append(f"- {reason} => كبار المستثمرين يشترون بهدوء")
        elif 'مطرقة' in reason:
            explanations.append(f"- {reason} => نمط انعكاسي ايجابي")
        elif 'ابتلاعية' in reason:
            explanations.append(f"- {reason} => نمط صعودي قوي")
        else:
            explanations.append(f"- {reason}")
    return "\n".join(explanations)

def learn_from_predictions():
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    if not learning_data.get('predictions'):
        return
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_preds = [p for p in learning_data['predictions'] if p.get('date') == yesterday]
    if not yesterday_preds:
        return
    print(f"مراجعة {len(yesterday_preds)} توقع...")
    correct, wrong = 0, 0
    for pred in yesterday_preds:
        try:
            symbol = pred['symbol']
            predicted_price = pred['price']
            predicted_action = pred['action']
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='2d', interval='1d')
            if len(data) < 2:
                continue
            actual_price = float(data['Close'].iloc[-1])
            price_change = ((actual_price - predicted_price) / predicted_price) * 100
            if predicted_action == 'buy':
                if price_change > 0:
                    correct += 1
                else:
                    wrong += 1
            else:
                if price_change < 0:
                    correct += 1
                else:
                    wrong += 1
        except:
            continue
    total = correct + wrong
    if total > 0:
        settings['total_predictions'] += total
        settings['correct_predictions'] += correct
        settings['accuracy_score'] = round(settings['correct_predictions'] / settings['total_predictions'], 2)
        current_rsi = settings['rsi_threshold']
        if settings['accuracy_score'] < 0.45 and current_rsi > 25:
            settings['rsi_threshold'] = max(25, current_rsi - 3)
            send_telegram(f"تحسين ذاتي! الدقة: {settings['accuracy_score']*100}%. RSI: {current_rsi} -> {settings['rsi_threshold']}. البوت اصبح اكثر انتقائية!")
        elif settings['accuracy_score'] > 0.70 and current_rsi < 45:
            settings['rsi_threshold'] = min(45, current_rsi + 2)
            send_telegram(f"تحسين ذاتي! الدقة: {settings['accuracy_score']*100}%. RSI: {current_rsi} -> {settings['rsi_threshold']}. البوت سيصطاد فرص اكثر!")
        settings['last_adjustment'] = yesterday
        save_json(SETTINGS_FILE, settings)
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        learning_data['predictions'] = [p for p in learning_data['predictions'] if p.get('date') >= week_ago]
        save_json(LEARNING_FILE, learning_data)

def analyze_stock(symbol, settings):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period='6mo', interval='1d')
        if len(data) < 50:
            return None
        current_price = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        change_percent = ((current_price - prev_close) / prev_close) * 100
        sma = float(data['Close'].rolling(window=50).mean().iloc[-1])
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = float(100 - (100 / (1 + (gain / loss).iloc[-1])))
        ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
        macd = float(ema_12.iloc[-1] - ema_26.iloc[-1])
        volume = float(data['Volume'].iloc[-1])
        avg_volume = float(data['Volume'].rolling(window=20).mean().iloc[-1])
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        adx = calculate_adx(data)
        obv_accumulation = calculate_obv(data)
        patterns = detect_patterns(data)
        high = data['High']
        low = data['Low']
        prev_close_col = data['Close'].shift(1)
        tr = pd.concat([high - low, (high - prev_close_col).abs(), (low - prev_close_col).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        stop_loss = round(current_price - (atr * 1.5), 2)
        target1 = round(current_price + (atr * 2), 2)
        target2 = round(current_price + (atr * 3), 2)
        capital = settings['capital']
        risk_percent = settings['risk_percent'] / 100.0
        risk_amount = capital * risk_percent
        if current_price > stop_loss and stop_loss > 0:
            risk_per_share = current_price - stop_loss
            position_size = int(risk_amount / risk_per_share)
            total_investment = position_size * current_price
        else:
            position_size = 0
            total_investment = 0
        score = 0
        reasons = []
        rsi_th = settings.get('rsi_threshold', 35)
        if rsi < rsi_th:
            score += 2
            reasons.append(f"RSI منخفض جداً ({rsi:.1f})")
        elif rsi < rsi_th + 10:
            score += 1
            reasons.append(f"RSI منخفض ({rsi:.1f})")
        if current_price > sma:
            score += 1
            reasons.append("السعر فوق المتوسط")
        else:
            reasons.append("السعر تحت المتوسط")
        if macd > 0:
            score += 1
            reasons.append("MACD ايجابي")
        if volume_ratio > 1.5:
            score += 1
            reasons.append(f"حجم تداول عالي ({volume_ratio:.1f}x)")
        if adx > 25:
            score += 1
            reasons.append(f"اتجاه قوي (ADX: {adx:.1f})")
        if obv_accumulation:
            score += 1
            reasons.append("تراكم مؤسساتي (OBV)")
        if patterns:
            score += len(patterns)
            reasons.extend(patterns)
        if score >= 6:
            rec = "صفقة قوية جداً"
            conf = "عالية جداً"
        elif score >= 5:
            rec = "شراء قوي"
            conf = "عالية"
        elif score >= 4:
            rec = "شراء"
            conf = "متوسطة"
        elif score >= 3:
            rec = "مراقبة"
            conf = "منخفضة"
        else:
            rec = "تجنب"
            conf = "ضعيفة"
        best_times = analyze_best_times(symbol)
        best_days = analyze_best_days(symbol)
        return {
            'symbol': symbol,
            'price': current_price,
            'change': round(change_percent, 2),
            'rsi': round(rsi, 1),
            'macd': round(macd, 2),
            'adx': round(adx, 1),
            'volume_ratio': round(volume_ratio, 2),
            'score': score,
            'recommendation': rec,
            'confidence': conf,
            'reasons': reasons,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'pos_size': position_size,
            'total_inv': total_investment,
            'risk_amt': round(risk_amount, 2),
            'best_times': best_times,
            'best_days': best_days,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        }
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

def find_affordable_stocks(settings, max_results=10):
    capital = settings['capital']
    risk_percent = settings['risk_percent'] / 100.0
    risk_amount = capital * risk_percent
    print(f"البحث عن اسهم مناسبة لميزانية ${capital}...")
    affordable_stocks = []
    stocks_to_check = ALL_US_STOCKS[:30]
    for symbol in stocks_to_check:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='5d', interval='1d')
            if len(data) < 3:
                continue
            current_price = float(data['Close'].iloc[-1])
            max_shares_by_capital = int(capital / current_price)
            max_shares_by_risk = int(risk_amount / (current_price * 0.02))
            position_size = min(max_shares_by_capital, max_shares_by_risk)
            if position_size >= 10:
                total_investment = position_size * current_price
                prev_close = float(data['Close'].iloc[-2])
                change_percent = ((current_price - prev_close) / prev_close) * 100
                delta = data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rsi = float(100 - (100 / (1 + (gain / loss).iloc[-1]))) if len(gain) > 0 else 50
                stock_name = STOCK_NAMES.get(symbol, symbol)
                affordable_stocks.append({
                    'symbol': symbol,
                    'name': stock_name,
                    'price': current_price,
                    'change': round(change_percent, 2),
                    'rsi': round(rsi, 1),
                    'position_size': position_size,
                    'total_investment': round(total_investment, 2),
                    'max_shares': max_shares_by_capital
                })
        except Exception as e:
            print(f"خطأ في {symbol}: {e}")
            continue
    affordable_stocks.sort(key=lambda x: x['price'])
    return affordable_stocks[:max_results]

def handle_chat(text):
    text_lower = text.lower().strip()
    settings = get_settings()
    mentioned_stocks = []
    for stock in STOCKS + ALL_US_STOCKS:
        if stock.lower() in text_lower or stock in text_lower:
            mentioned_stocks.append(stock)
    if mentioned_stocks:
        symbol = mentioned_stocks[0]
        result = analyze_stock(symbol, settings)
        if result:
            stock_name = STOCK_NAMES.get(symbol, symbol)
            msg = f"تحليل {stock_name} ({symbol}):\n\n"
            msg += f"السعر الحالي: ${result['price']} ({result['change']:+.2f}%)\n"
            msg += f"RSI: {result['rsi']} | MACD: {result['macd']} | ADX: {result['adx']}\n"
            msg += f"التوصية: {result['recommendation']} ({result['confidence']})\n"
            msg += f"النقاط: {result['score']}/8\n\n"
            msg += explain_recommendation(result)
            msg += "\n\n"
            msg += f"خطة التداول المقترحة:\n"
            msg += f"- عدد الاسهم: {result['pos_size']} سهم\n"
            msg += f"- قيمة الاستثمار: ${result['total_inv']}\n"
            msg += f"- المخاطرة: ${result['risk_amt']}\n"
            msg += f"- وقف الخسارة: ${result['stop_loss']}\n"
            msg += f"- الهدف الاول: ${result['target1']}\n"
            msg += f"- الهدف الثاني: ${result['target2']}\n"
            if result.get('best_times'):
                msg += f"\nافضل اوقات الشراء:\n"
                for h, v in result['best_times']:
                    msg += f"- الساعة {h}:00 (عائد متوقع: +{v}%)\n"
            if result.get('best_days'):
                msg += f"\nافضل ايام التداول:\n"
                for d, v in result['best_days']:
                    msg += f"- {d} (عائد متوقع: +{v}%)\n"
            return msg
        else:
            return f"لم اتمكن من تحليل {symbol} حالياً."
    if any(word in text_lower for word in ['اسهم رخيصة', 'رخيصة', 'cheap', 'affordable', 'ميزانيتي', 'budget', 'اقدر اشتري', 'مناسب لميزانيتي', 'اسهم مناسبة']):
        affordable = find_affordable_stocks(settings, max_results=8)
        if affordable:
            msg = f"اسهم مناسبة لميزانيتك (${settings['capital']}):\n\nيمكنك شراء 10 اسهم على الاقل:\n\n"
            for stock in affordable:
                msg += f"{stock['name']} ({stock['symbol']})\n"
                msg += f"السعر: ${stock['price']} ({stock['change']:+.2f}%)\n"
                msg += f"RSI: {stock['rsi']}\n"
                msg += f"يمكنك شراء: {stock['position_size']} سهم\n"
                msg += f"التكلفة: ${stock['total_investment']}\n\n"
            msg += f"نصيحة: استخدم /stock [رمز] لتحليل مفصل!"
            return msg
        else:
            return "لم اجد اسهم مناسبة لميزانيتك."
    if any(word in text_lower for word in ['اخبار', 'news', 'تقرير يومي']):
        news = get_daily_news()
        if news:
            msg = "آخر اخبار السوق:\n\n"
            for item in news[:5]:
                stock_name = STOCK_NAMES.get(item['symbol'], item['symbol'])
                msg += f"{stock_name} ({item['symbol']}): {item['title']}\n"
                msg += f"{item['publisher']} | {item['time']}\n\n"
            return msg
        else:
            return "لا توجد اخبار متاحة حالياً."
    if any(word in text_lower for word in ['rsi', 'ما هو rsi', 'شرح rsi']):
        return "مؤشر RSI:\n\nRSI < 30: مباع بشكل زائد - فرصة شراء\nRSI > 70: مشتري بشكل زائد - قد ينخفض\nRSI 30-70: منطقة محايدة\n\nالبوت يستخدم RSI < 35 كاشارة شراء."
    elif any(word in text_lower for word in ['macd', 'ما هو macd']):
        return "مؤشر MACD:\n\nMACD > 0: زخم صعودي\nMACD < 0: زخم هبوطي"
    elif any(word in text_lower for word in ['adx', 'ما هو adx']):
        return "مؤشر ADX:\n\nADX > 25: اتجاه قوي\nADX < 25: اتجاه ضعيف"
    elif any(word in text_lower for word in ['obv', 'تراكم']):
        return "مؤشر OBV:\n\nOBV مرتفع: تراكم مؤسساتي\nOBV منخفض: توزيع"
    elif any(word in text_lower for word in ['وقف الخسارة', 'stop loss', 'وقف']):
        return f"وقف الخسارة:\n\nيحمي راس مالك من خسائر اكبر.\n\nمن اعداداتك:\n- راس المال: ${settings['capital']}\n- المخاطرة: {settings['risk_percent']}% = ${settings['capital'] * settings['risk_percent'] / 100}\n\nالتزم بوقف الخسارة دائماً!"
    elif any(word in text_lower for word in ['كيف', 'help', 'مساعدة']):
        return "كيف تستخدم البوت:\n\nاكتب رمز سهم: TSLA, AAPL, MSFT\nالاوامر: /settings, /status, /stock, /affordable, /news\nاسال عن: RSI, MACD, ADX, OBV, وقف الخسارة\nاسهم رخيصة او اخبار السوق"
    elif any(word in text_lower for word in ['افضل سهم', 'best stock', 'اشتر', 'شراء']):
        results = []
        for symbol in STOCKS:
            result = analyze_stock(symbol, settings)
            if result and result['score'] >= 4:
                results.append(result)
        if results:
            results.sort(key=lambda x: x['score'], reverse=True)
            msg = "افضل الاسهم للشراء:\n\n"
            for r in results[:3]:
                stock_name = STOCK_NAMES.get(r['symbol'], r['symbol'])
                msg += f"{stock_name} ({r['symbol']})\n"
                msg += f"${r['price']} ({r['change']:+.2f}%)\n"
                msg += f"{r['recommendation']} (نقاط: {r['score']})\n"
                msg += f"SL: ${r['stop_loss']} | T1: ${r['target1']}\n\n"
            return msg
        else:
            return "لا توجد فرص شراء قوية حالياً."
    elif any(word in text_lower for word in ['مرحبا', 'هلا', 'سلام', 'hi', 'hello']):
        return "اهلاً!\n\nانا بوت تحليل الاسهم الذكي.\n\nيمكنني:\n- تحليل اي سهم\n- الاجابة عن المؤشرات\n- اقتراح افضل الفرص\n- البحث عن اسهم مناسبة لميزانيتك\n- ارسال اخبار السوق\n\nجرب: TSLA او اسهم رخيصة او اخبار"
    elif any(word in text_lower for word in ['شكر', 'thanks', 'ممتاز']):
        return "العفو!\n\nهل تريد تحليل سهم او لديك سؤال اخر؟"
    elif any(word in text_lower for word in ['دقة', 'accuracy', 'اداء']):
        return f"اداء البوت:\n\nالدقة: {settings['accuracy_score']*100}%\nالصحيحة: {settings['correct_predictions']}\nالتوقعات: {settings['total_predictions']}\nRSI: {settings['rsi_threshold']}\n\nالبوت يتعلم ذاتياً كل ساعة!"
    else:
        return "لم افهم تماماً.\n\nجرب:\n- رمز سهم: TSLA, AAPL\n- اسهم رخيصة\n- اخبار السوق\n- /help للاوامر"

def process_message(text, settings):
    if text == '/settings':
        msg = f"اعدادات البوت الذكية:\n"
        msg += f"راس المال: ${settings['capital']}\n"
        msg += f"المخاطرة: {settings['risk_percent']}%\n"
        msg += f"معيار RSI: {settings['rsi_threshold']} (يتعدل تلقائياً)\n"
        msg += f"الدقة: {settings['accuracy_score']*100}%\n"
        msg += f"التوقعات: {settings['total_predictions']}\n"
        msg += f"الصحيحة: {settings['correct_predictions']}\n\n"
        msg += f"انماط الاخطاء:\n"
        mistakes = settings.get('mistake_patterns', {})
        msg += f"- RSI مرتفع: {mistakes.get('high_rsi', 0)}\n"
        msg += f"- حجم منخفض: {mistakes.get('low_volume', 0)}\n"
        msg += f"- اتجاه ضعيف: {mistakes.get('weak_trend', 0)}\n"
        msg += f"- MACD خاطئ: {mistakes.get('wrong_macd', 0)}"
        send_telegram(msg)
        print("تم ارسال /settings")
    elif text == '/help':
        msg = "اوامر البوت:\n\nالاوامر:\n- /settings - اعدادات البوت\n- /status - حالة التعلم\n- /stock [رمز] - تحليل سهم\n- /affordable - اسهم مناسبة لميزانيتك\n- /news - اخبار السوق\n- /learn - مراجعة ذاتية\n\nالمحادثة:\n- اكتب رمز سهم: TSLA, AAPL\n- اسهم رخيصة\n- اخبار السوق\n- اسال عن: RSI, MACD, ADX, OBV"
        send_telegram(msg)
        print("تم ارسال /help")
    elif text == '/learn':
        learn_from_predictions()
        send_telegram("تمت المراجعة الذاتية!")
        print("تم ارسال /learn")
    elif text == '/news':
        send_telegram("جاري جلب الاخبار...")
        send_daily_news_report()
        print("تم ارسال /news")
    elif text.startswith('/stock '):
        symbol = text.split()[1].upper()
        result = analyze_stock(symbol, settings)
        if result:
            stock_name = STOCK_NAMES.get(result['symbol'], result['symbol'])
            msg = f"تحليل {stock_name} ({result['symbol']}):\n"
            msg += f"السعر: ${result['price']} ({result['change']:+.2f}%)\n"
            msg += f"RSI: {result['rsi']} | MACD: {result['macd']} | ADX: {result['adx']}\n"
            msg += f"{result['recommendation']} ({result['confidence']})\n"
            msg += f"النقاط: {result['score']}/8\n\n"
            msg += explain_recommendation(result)
            msg += "\n\n"
            msg += f"الاسباب:\n" + "\n".join(['- ' + r for r in result['reasons']]) + f"\n\n"
            msg += f"خطة التداول:\n"
            msg += f"- العدد: {result['pos_size']} سهم\n"
            msg += f"- الاستثمار: ${result['total_inv']}\n"
            msg += f"- المخاطرة: ${result['risk_amt']}\n"
            msg += f"- SL: ${result['stop_loss']}\n"
            msg += f"- T1: ${result['target1']}\n"
            msg += f"- T2: ${result['target2']}\n\n"
            if result.get('best_times'):
                msg += f"افضل اوقات الشراء:\n"
                for h, v in result['best_times']:
                    msg += f"- الساعة {h}:00 (عائد: +{v}%)\n"
            if result.get('best_days'):
                msg += f"\nافضل ايام التداول:\n"
                for d, v in result['best_days']:
                    msg += f"- {d} (+{v}%)\n"
            send_telegram(msg)
            print(f"تم ارسال /stock {symbol}")
        else:
            send_telegram(f"لا بيانات لـ {symbol}")
    elif text == '/affordable':
        send_telegram("جاري البحث عن اسهم مناسبة...")
        affordable = find_affordable_stocks(settings, max_results=8)
        if affordable:
            msg = f"اسهم مناسبة لميزانيتك (${settings['capital']}):\n\nيمكنك شراء 10 اسهم على الاقل:\n\n"
            for stock in affordable:
                msg += f"{stock['name']} ({stock['symbol']})\n"
                msg += f"السعر: ${stock['price']} ({stock['change']:+.2f}%)\n"
                msg += f"RSI: {stock['rsi']}\n"
                msg += f"يمكنك شراء: {stock['position_size']} سهم\n"
                msg += f"التكلفة: ${stock['total_investment']}\n\n"
            msg += f"استخدم /stock [رمز] لتحليل مفصل!"
            send_telegram(msg)
            print("تم ارسال /affordable")
        else:
            send_telegram("لم اجد اسهم مناسبة.")
    elif text == '/status':
        learning_data = load_json(LEARNING_FILE, {'predictions': []})
        today_preds = len([p for p in learning_data['predictions'] if p.get('date') == datetime.utcnow().strftime('%Y-%m-%d')])
        send_telegram(f"حالة التعلم:\nالدقة: {settings['accuracy_score']*100}%\nRSI: {settings['rsi_threshold']}\nتوقعات اليوم: {today_preds}\nالبوت يتعلم ذاتياً كل ساعة!")
        print("تم ارسال /status")
    elif text and not text.startswith('/'):
        response_text = handle_chat(text)
        if response_text:
            send_telegram(response_text)
            print(f"تم الرد على: {text[:30]}")

def handle_commands():
    print("بدء معالجة الاوامر...")
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    last_update_id = get_last_update_id()
    
    try:
        url = f"{url_base}/getUpdates?offset={last_update_id + 1}&limit=100&timeout=5"
        print(f"الاتصال بـ Telegram (من update {last_update_id})...")
        response = requests.get(url, timeout=10).json()
        
        if not response.get('ok'):
            print("فشل الاتصال")
            return
        
        results = response.get('result', [])
        print(f"عدد الرسائل الجديدة: {len(results)}")
        
        if len(results) == 0:
            print("لا توجد رسائل جديدة")
            return
        
        settings = get_settings()
        max_update_id = last_update_id
        
        for update in results:
            update_id = update['update_id']
            if update_id > max_update_id:
                max_update_id = update_id
            
            message = update.get('message', {})
            text = message.get('text', '').strip()
            chat_id = str(message.get('chat', {}).get('id', ''))
            
            print(f"رسالة من {chat_id}: {text[:50]}")
            
            if chat_id != CHAT_ID:
                print("Chat ID غير مطابق")
                continue
            
            try:
                process_message(text, settings)
            except Exception as e:
                print(f"خطأ في معالجة الامر: {e}")
                send_telegram(f"حدث خطأ: {e}")
        
        save_last_update_id(max_update_id)
        print(f"تم حفظ آخر update_id: {max_update_id}")
    
    except Exception as e:
        print(f"خطأ في handle_commands: {e}")

def run_scan():
    print("بدء فحص السوق...")
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    now = datetime.utcnow()
    today = now.strftime('%Y-%m-%d')
    results = []
    strong_alerts = []
    for symbol in settings.get('stocks', STOCKS):
        try:
            result = analyze_stock(symbol, settings)
            if result:
                results.append(result)
                action = 'buy' if result['score'] >= 3 else 'avoid'
                learning_data['predictions'].append({
                    'symbol': symbol,
                    'price': result['price'],
                    'action': action,
                    'rsi': result['rsi'],
                    'score': result['score'],
                    'volume_ratio': result.get('volume_ratio', 1),
                    'adx': result.get('adx', 0),
                    'macd': result.get('macd', 0),
                    'date': today,
                    'time': now.strftime('%H:%M'),
                    'timestamp': now.strftime('%Y-%m-%d %H')
                })
                if result['score'] >= 5:
                    strong_alerts.append(result)
        except Exception as e:
            print(f"خطأ في {symbol}: {e}")
    save_json(LEARNING_FILE, learning_data)
    if results:
        results.sort(key=lambda x: x['score'], reverse=True)
        msg = f"فحص السوق (كل 5 دقائق)\n{now.strftime('%H:%M')} UTC\n"
        msg += f"الدقة: {settings['accuracy_score']*100}% | RSI: {settings['rsi_threshold']}\n\n"
        msg += f"افضل 3 فرص:\n\n"
        for r in results[:3]:
            stock_name = STOCK_NAMES.get(r['symbol'], r['symbol'])
            msg += f"{stock_name} ({r['symbol']}) ({r['change']:+.2f}%)\n"
            msg += f"السعر: ${r['price']} | RSI: {r['rsi']} | ADX: {r['adx']}\n"
            msg += f"{r['recommendation']} (نقاط: {r['score']})\n"
            msg += f"{', '.join(r['reasons'])}\n"
            msg += f"SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n\n"
            msg += explain_recommendation(r)
            msg += "\n\n"
            if r.get('best_times'):
                msg += f"افضل وقت: {r['best_times'][0][0]}:00 (عائد: +{r['best_times'][0][1]}%)\n"
            if r.get('best_days'):
                msg += f"افضل يوم: {r['best_days'][0][0]} (+{r['best_days'][0][1]}%)\n"
            msg += "\n"
        if strong_alerts:
            msg += f"\nفرص قوية جداً!\n\n"
            for r in strong_alerts:
                stock_name = STOCK_NAMES.get(r['symbol'], r['symbol'])
                msg += f"{stock_name} ({r['symbol']}) - {r['recommendation']}\n"
                msg += f"${r['price']} | RSI: {r['rsi']}\n"
                msg += f"النقاط: {r['score']}/8\n"
                msg += f"SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n\n"
                msg += explain_recommendation(r) + "\n\n"
                if r.get('best_times'):
                    msg += f"اشتري الساعة: {r['best_times'][0][0]}:00\n"
                if r.get('best_days'):
                    msg += f"افضل يوم: {r['best_days'][0][0]}\n"
                msg += f"العدد: {r['pos_size']} سهم (${r['total_inv']})\n\n"
        send_telegram(msg)
        print(f"تم ارسال التقرير ({len(strong_alerts)} فرصة قوية)")
    else:
        print("لا توجد بيانات.")
    print("انتهى الفحص")

if __name__ == '__main__':
    print("بدء البوت الذكي المتعلم...")
    print("1. معالجة الاوامر...")
    handle_commands()
    now = datetime.utcnow()
    print("2. التعلم السريع...")
    fast_learning()
    if now.hour == 10:
        print("3. المراجعة الذاتية اليومية...")
        learn_from_predictions()
    if now.hour == 9 and now.minute < 10:
        print("4. تقرير الاخبار اليومي...")
        send_daily_news_report()
    print("5. فحص السوق...")
    run_scan()
    print("انتهى البوت")
