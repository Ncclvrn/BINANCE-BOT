# Binance Trading Bot - Spot & Futures (con Telegram + TP/SL + Report)
import time
import pandas as pd
import schedule
import ccxt
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
import requests

# Load API keys and config
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance clients
binance_spot = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

binance_futures = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# Config
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"
RSI_PERIOD = 14
MA_PERIOD = 20
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
CAPITAL_USAGE = 0.60
LEVERAGE = 2
STOP_LOSS_PCT = 0.01
TAKE_PROFIT_PCT = 0.02


def get_balance_usdt(client):
    balance = client.fetch_balance()
    usdt = balance['total']['USDT']
    return usdt * CAPITAL_USAGE

def get_ohlcv(client):
    ohlcv = client.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def analyze_market():
    df_spot = get_ohlcv(binance_spot)
    analyze(df_spot, binance_spot, 'spot')

    df_futures = get_ohlcv(binance_futures)
    analyze(df_futures, binance_futures, 'futures')

def analyze(df, client, mode):
    rsi = RSIIndicator(close=df['close'], window=RSI_PERIOD).rsi()
    sma = SMAIndicator(close=df['close'], window=MA_PERIOD).sma_indicator()
    current_price = df['close'].iloc[-1]

    is_bullish = current_price > sma.iloc[-1]
    last_rsi = rsi.iloc[-1]

    if last_rsi < RSI_OVERSOLD and is_bullish:
        place_order("buy", current_price, client, mode)
    elif last_rsi > RSI_OVERBOUGHT and not is_bullish:
        place_order("sell", current_price, client, mode)

def place_order(side, price, client, mode):
    balance_to_use = get_balance_usdt(client) / 2
    qty = round(balance_to_use / price, 6)
    stop_loss_price = round(price * (1 - STOP_LOSS_PCT), 2) if side == "buy" else round(price * (1 + STOP_LOSS_PCT), 2)
    take_profit_price = round(price * (1 + TAKE_PROFIT_PCT), 2) if side == "buy" else round(price * (1 - TAKE_PROFIT_PCT), 2)

    message = f"[{mode.upper()}] {side.upper()} @ {price}, Qty: {qty}, SL: {stop_loss_price}, TP: {take_profit_price}"
    print(message)
    send_telegram(message)

    order = client.create_order(
        symbol=SYMBOL,
        side=side,
        type="MARKET",
        amount=qty,
        params={
            "stopLossPrice": stop_loss_price,
            "takeProfitPrice": take_profit_price
        }
    )

    print("ORDER EXECUTED:", order)

    with open("profit_log.txt", "a") as log:
        log.write(message + "\n")

def report():
    print("\n--- SENDING REPORT ---")
    try:
        with open("profit_log.txt", "r") as log:
            content = log.read()
        send_email("Binance Trading Bot Report", content)
        send_telegram("\U0001F4C8 Binance Bot Report Sent")
        print("Report sent via email and Telegram.")
    except Exception as e:
        print("Error sending report:", e)

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

def test_telegram():
    send_telegram("✅ Test Telegram: il bot è attivo e collegato correttamente.")

def check_mode():
    mode_message = "✅ Il bot è attivo su Binance MAINNET (mercato REALE)."
    print(mode_message)
    send_telegram(mode_message)

schedule.every(15).minutes.do(analyze_market)
schedule.every(12).hours.do(report)

if __name__ == "__main__":
    print("Starting Binance Spot & Futures Bot (completo con TP/SL + Email + Telegram)...")
    test_telegram()
    check_mode()
    report()
    while True:
        schedule.run_pending()
        time.sleep(1)
