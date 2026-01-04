# Crypto Alert Bot (Upgraded)

Realtimes Binance Futures data -> build 1s candles -> resample 5m/15m/1h/4h -> compute RSI/EMA/MACD -> alert to Telegram.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env (Telegram token/chat id, TOP_N, modes...)
python -m app.main
```

## Modes
- `ALERT_MODE=signal` : trend-follow (HTF EMA + regime + RSI timing + MACD strength)
- `ALERT_MODE=rsi` : RSI threshold/cross
- `ALERT_MODE=macd` : MACD histogram cross 0

## Notes
If you see `Binance API Error: Status 451`, Binance is blocking your location/IP. You need a permitted network/location to fetch symbols and connect WS.
