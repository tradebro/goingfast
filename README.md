# Going Fast

A Sanic based [TradingView](https://www.tradingview.com/gopro/?share_your_love=tista) alerts trader. Trading actions are run in the background to comply with TradingView's 3 seconds must reply and close connection rule.

## Endpoint

```
[POST] /webhook

+ Request (application/json)

        {
            "close": 11382.11,
            "indicator": "Bayesian SMI Oscillator",
            "exchange": "Coinbase",
            "pair": "BTCUSD",
            "action": "Long"
        }

+ Response 200
```

## Env Vars

| Name | Description |
| :--- | :--- |
| `APP_HOST` | Required string |
| `APP_PORT` | Required string |
| `APP_DEBUG` | Required string, 0 or 1 - when enabled will print debug logs |
| `API_KEY` | Required string |
| `API_SECRET` | Required string |
| `TRADER` | Required string, the exchange to trade |
| `LEVERAGE` | Required string, for leveraged exchanges |
| `STOP_DELTA` | Required string, stop trigger price calculated from this |
| `TP_DELTA` | Required string |
| `CAPITAL_IN_USD` | Required string |
| `TELEGRAM_TOKEN` | Required string |
| `TELEGRAM_USER_ID` | Required string |

