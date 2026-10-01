import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================
# إعدادات تليجرام
# ============================================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8832925625:AAH40Jt4Ux2zDZXKA7cUW-LQtl6NtvcOhHY')
CHAT_ID = os.environ.get('CHAT_ID', '208377256')

STOCKS = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'NFLX', 'SPY']

# ملفات الذاكرة
LEARNING_FILE = 'learning_data.json'
SETTINGS_FILE = 'bot_settings.json'
TIMING_FILE = 'timing_data.json'

def load_json(filename, default=None):
    if default is None: default = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)

def get_settings():
    defaults = {
        'capital': 10000,
        'risk_percent': 2.0,
        'rsi_threshold': 35,
        'accuracy_score': 0,
        'total_predictions': 0,
        'correct_predictions': 0,
        'last_adjustment': None
    }
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
# ⏰ تحليل أفضل أوقات التداول
# ============================================
def analyze_best_times(symbol):
    try:
        data = yf.download(symbol, period='3mo', interval='30m', progress=False)
        if len(data) < 100: return None
        
        data['hour'] = data.index.hour
        data['return'] = data['Close'].pct_change() * 100
        
        hourly_stats = data.groupby('hour')['return'].mean()
        best_times = hourly_stats.nlargest(3)
        
        return [(int(h), round(float(v), 2)) for h, v in best_times.items()]
    except:
        return None

# ============================================
# 📅 تحليل أفضل أيام الأسبوع
# ============================================
def analyze_best_days(symbol):
    try:
        data = yf.download(symbol, period='6mo', interval='1d', progress=False)
        if len(data) < 100: return None
        
        data['day_of_week'] = data.index.dayofweek
        data['return'] = data['Close'].pct_change() * 100
        
        days_arabic = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة'}
        day_stats = data.groupby('day_of_week')['return'].mean()
        
        best_days = day_stats.nlargest(3)
        return [(days_arabic.get(int(d), d), round(float(v), 2)) for d, v in best_days.items()]
    except:
        return None

# ============================================
# 🏦 مؤشر OBV
# ============================================
def calculate_obv(data):
    try:
        close = data['Close']
        volume = data['Volume']
        direction = np.sign(close.diff())
        obv = (direction * volume).fillna(0).cumsum()
        obv_sma = obv.rolling(window=20).mean()
        current_obv = float(obv.iloc[-1])
        current_obv_sma = float(obv_sma.iloc[-1])
        return (current_obv > current_obv_sma)
    except:
        return False

# ============================================
# 💪 مؤشر ADX
# ============================================
def calculate_adx(data, period=14):
    try:
        high, low, close = data['High'], data['Low'], data['Close']
        plus_dm = high.diff(); plus_dm[plus_dm < 0] = 0
        minus_dm = low.diff(); minus_dm[minus_dm > 0] = 0
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(window=period).mean()
        return float(adx.iloc[-1]) if not adx.empty else 0
    except:
        return 0

# ============================================
# 🕯️ كشف أنماط الشموع
# ============================================
def detect_patterns(data):
    patterns = []
    try:
        if len(data) < 3: return patterns
        
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
            patterns.append("🔨 مطرقة (صعود)")
        
        if close_p > open_p and prev_close < prev_open and close_p > prev_open and open_p < prev_close:
            patterns.append("📈 ابتلاعية صعودية")
        
        if body < (high_p - low_p) * 0.1:
            patterns.append("⚖️ دوجي (تردد)")
    except:
        pass
    
    return patterns

# ============================================
# 🧠 نظام التعلم الذاتي
# ============================================
def learn_from_predictions():
    settings = get_settings()
    learning_data = load_json(LEARNING_FILE, {'predictions': []})
    
    if not learning_data.get('predictions'):
        return
    
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_preds = [p for p in learning_data['predictions'] if p.get('date') == yesterday]
    
    if not yesterday_preds:
        return
    
    print(f"🧠 مراجعة {len(yesterday_preds)} توقع...")
    
    correct = 0
    wrong = 0
    
    for pred in yesterday_preds:
        try:
            symbol = pred['symbol']
            predicted_price = pred['price']
            predicted_action = pred['action']
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='2d', interval='1d')
            if len(data) < 2: continue
            
            actual_price = float(data['Close'].iloc[-1])
            price_change = ((actual_price - predicted_price) / predicted_price) * 100
            
            if predicted_action == 'buy':
                if price_change > 0: correct += 1
                else: wrong += 1
            else:
                if price_change < 0: correct += 1
                else: wrong += 1
        except:
            continue
    
    total = correct + wrong
    if total > 0:
        daily_accuracy = correct / total
        settings['total_predictions'] += total
        settings['correct_predictions'] += correct
        settings['accuracy_score'] = round(settings['correct_predictions'] / settings['total_predictions'], 2)
        
        current_rsi = settings['rsi_threshold']
        
        if settings['accuracy_score'] < 0.45 and current_rsi > 25:
            settings['rsi_threshold'] = max(25, current_rsi - 3)
            send_telegram(f"🧠 <b>تحسين ذاتي!</b>\n\nالدقة: {settings['accuracy_score']*100}%\nتم تشديد RSI: {current_rsi} → {settings['rsi_threshold']}\n\nالبوت أصبح أكثر انتقائية!")
        
        elif settings['accuracy_score'] > 0.70 and current_rsi < 45:
            settings['rsi_threshold'] = min(45, current_rsi + 2)
            send_telegram(f" <b>تحسين ذاتي!</b>\n\nالدقة: {settings['accuracy_score']*100}%\nتم توسيع RSI: {current_rsi} → {settings['rsi_threshold']}\n\nالبوت سيصطاد فرص أكثر!")
        
        settings['last_adjustment'] = yesterday
        save_json(SETTINGS_FILE, settings)
        
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        learning_data['predictions'] = [p for p in learning_data['predictions'] if p.get('date') >= week_ago]
        save_json(LEARNING_FILE, learning_data)

# ============================================
# 📊 تحليل السهم الكامل
# ============================================
def analyze_stock(symbol, settings):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period='6mo', interval='1d')
        if len(data) < 50: return None
        
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
        
        high, low, prev_close_col = data['High'], data['Low'], data['Close'].shift(1)
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
            position_size, total_investment = 0, 0
        
        score, reasons = 0, []
        rsi_th = settings.get('rsi_threshold', 35)
        
        if rsi < rsi_th: score += 2; reasons.append(f"RSI منخفض جداً ({rsi:.1f}) 📉")
        elif rsi < rsi_th + 10: score += 1; reasons.append(f"RSI منخفض ({rsi:.1f})")
        
        if current_price > sma: score += 1; reasons.append("السعر فوق المتوسط 📈")
        else: reasons.append("السعر تحت المتوسط 📉")
        
        if macd > 0: score += 1; reasons.append("MACD إيجابي ✅")
        if volume_ratio > 1.5: score += 1; reasons.append(f"حجم تداول عالي ({volume_ratio:.1f}x) 💪")
        if adx > 25: score += 1; reasons.append(f"اتجاه قوي (ADX: {adx:.1f}) 💪")
        if obv_accumulation: score += 1; reasons.append("🏦 تراكم مؤسساتي (OBV)")
        if patterns:
            score += len(patterns)
            reasons.extend(patterns)
        
        if score >= 6: rec, conf = "🚨 صفقة قوية جداً", "عالية جداً"
        elif score >= 5: rec, conf = "✅ شراء قوي", "عالية"
        elif score >= 4: rec, conf = "🟡 شراء", "متوسطة"
        elif score >= 3: rec, conf = "👀 مراقبة", "منخفضة"
        else: rec, conf = " تجنب", "ضعيفة"

        # تحليل التوقيت
        best_times = analyze_best_times(symbol)
        best_days = analyze_best_days(symbol)

        return {
            'symbol': symbol, 'price': current_price, 'change': round(change_percent, 2),
            'rsi': round(rsi, 1), 'macd': round(macd, 2), 'adx': round(adx, 1),
            'score': score, 'recommendation': rec, 'confidence': conf, 'reasons': reasons,
            'stop_loss': stop_loss, 'target1': target1, 'target2': target2,
            'pos_size': position_size, 'total_inv': total_investment, 'risk_amt': round(risk_amount, 2),
            'best_times': best_times, 'best_days': best_days,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        }
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

# ============================================
# 🎯 فحص السوق
# ============================================
def run_scan():
    print(" بدء فحص السوق...")
    
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
                    'symbol': symbol, 'price': result['price'], 'action': action,
                    'rsi': result['rsi'], 'score': result['score'],
                    'date': today, 'time': now.strftime('%H:%M')
                })
                
                if result['score'] >= 5:
                    strong_alerts.append(result)
        except Exception as e:
            print(f"خطأ في {symbol}: {e}")
    
    save_json(LEARNING_FILE, learning_data)
    
    if results:
        results.sort(key=lambda x: x['score'], reverse=True)
        
        msg = f"📊 <b>فحص السوق (كل 5 دقائق)</b>\n🕒 {now.strftime('%H:%M')} UTC\n"
        msg += f"🧠 الدقة: {settings['accuracy_score']*100}% | RSI: {settings['rsi_threshold']}\n\n"
        
        msg += f"<b>🏆 أفضل 3 فرص:</b>\n\n"
        for r in results[:3]:
            msg += f" <b>{r['symbol']}</b> ({r['change']:+.2f}%)\n"
            msg += f"💰 السعر: ${r['price']} | RSI: {r['rsi']} | ADX: {r['adx']}\n"
            msg += f"{r['recommendation']} (نقاط: {r['score']})\n"
            msg += f"📝 {', '.join(r['reasons'])}\n"
            msg += f"🛡️ SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n"
            
            if r.get('best_times'):
                msg += f"⏰ أفضل وقت: {r['best_times'][0][0]}:00 (عائد: +{r['best_times'][0][1]}%)\n"
            if r.get('best_days'):
                msg += f" أفضل يوم: {r['best_days'][0][0]} (+{r['best_days'][0][1]}%)\n"
            msg += "\n"
        
        if strong_alerts:
            msg += f"\n🚨 <b>فرص قوية جداً!</b>\n\n"
            for r in strong_alerts:
                msg += f"🔥 <b>{r['symbol']}</b> - {r['recommendation']}\n"
                msg += f"💰 ${r['price']} | RSI: {r['rsi']}\n"
                msg += f" النقاط: {r['score']}/8\n"
                msg += f"🛡️ SL: ${r['stop_loss']} | T1: ${r['target1']} | T2: ${r['target2']}\n"
                
                if r.get('best_times'):
                    msg += f"⏰ اشترِ الساعة: {r['best_times'][0][0]}:00\n"
                if r.get('best_days'):
                    msg += f"📅 أفضل يوم: {r['best_days'][0][0]}\n"
                msg += f"💰 العدد: {r['pos_size']} سهم (${r['total_inv']})\n\n"
        
        send_telegram(msg)
        print(f"✅ تم إرسال التقرير ({len(strong_alerts)} فرصة قوية)")
    else:
        print("لا توجد بيانات.")
    
    print("✅ انتهى الفحص")

# ============================================
#  أوامر تليجرام
# ============================================
def handle_commands():
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    last_update_id = 0
    
    try:
        url = f"{url_base}/getUpdates?offset={last_update_id + 1}&timeout=5"
        response = requests.get(url, timeout=10).json()
        if not response.get('ok'): return
        
        for update in response.get('result', []):
            last_update_id = update['update_id']
            message = update.get('message', {})
            text = message.get('text', '').strip()
            chat_id = str(message.get('chat', {}).get('id', ''))
            
            if chat_id != CHAT_ID: continue
            settings = get_settings()
            
            if text == '/settings':
                msg = f"⚙️ <b>إعدادات البوت الذكية:</b>\n"
                msg += f"💰 رأس المال: ${settings['capital']}\n"
                msg += f"⚠️ المخاطرة: {settings['risk_percent']}%\n"
                msg += f"🧠 معيار RSI: {settings['rsi_threshold']} (يتعدل تلقائياً)\n"
                msg += f"🎯 الدقة: {settings['accuracy_score']*100}%\n"
                msg += f"📊 التوقعات: {settings['total_predictions']}\n"
                msg += f"✅ الصحيحة: {settings['correct_predictions']}"
                send_telegram(msg)
            
            elif text == '/learn':
                learn_from_predictions()
                send_telegram("✅ تمت المراجعة الذاتية!")
            
            elif text.startswith('/stock '):
                symbol = text.split()[1].upper()
                result = analyze_stock(symbol, settings)
                if result:
                    msg = f" <b>تحليل {result['symbol']}:</b>\n"
                    msg += f"💰 السعر: ${result['price']} ({result['change']:+.2f}%)\n"
                    msg += f"📈 RSI: {result['rsi']} | MACD: {result['macd']} | ADX: {result['adx']}\n"
                    msg += f"🎯 {result['recommendation']} ({result['confidence']})\n"
                    msg += f"⭐ النقاط: {result['score']}/8\n\n"
                    msg += f"📝 الأسباب:\n" + "\n".join(['• ' + r for r in result['reasons']]) + f"\n\n"
                    msg += f"💰 خطة التداول:\n"
                    msg += f"• العدد: {result['pos_size']} سهم\n"
                    msg += f"• الاستثمار: ${result['total_inv']}\n"
                    msg += f"• المخاطرة: ${result['risk_amt']}\n"
                    msg += f"🛡️ SL: ${result['stop_loss']}\n"
                    msg += f"🎯 T1: ${result['target1']}\n"
                    msg += f" T2: ${result['target2']}\n\n"
                    
                    if result.get('best_times'):
                        msg += f"⏰ <b>أفضل أوقات الشراء:</b>\n"
                        for h, v in result['best_times']:
                            msg += f"• الساعة {h}:00 (عائد: +{v}%)\n"
                    
                    if result.get('best_days'):
                        msg += f"\n📅 <b>أفضل أيام التداول:</b>\n"
                        for d, v in result['best_days']:
                            msg += f"• {d} (+{v}%)\n"
                    
                    send_telegram(msg)
                else:
                    send_telegram(f"❌ لا بيانات لـ {symbol}")
            
            elif text == '/status':
                learning_data = load_json(LEARNING_FILE, {'predictions': []})
                today_preds = len([p for p in learning_data['predictions'] if p.get('date') == datetime.utcnow().strftime('%Y-%m-%d')])
                send_telegram(f" <b>حالة التعلم:</b>\n"
                            f"🎯 الدقة: {settings['accuracy_score']*100}%\n"
                            f"⚙️ RSI: {settings['rsi_threshold']}\n"
                            f"📝 توقعات اليوم: {today_preds}\n"
                            f"💡 البوت يتعلم ذاتياً كل يوم!")
    
    except Exception as e:
        print(f"خطأ: {e}")

# ============================================
# 🚀 التشغيل الرئيسي
# ============================================
if __name__ == '__main__':
    print("🚀 بدء البوت الذكي المتعلم...")
    
    handle_commands()
    
    now = datetime.utcnow()
    if now.hour == 10:
        print(" بدء المراجعة الذاتية...")
        learn_from_predictions()
    
    run_scan()
    
    print("✅ انتهى")
