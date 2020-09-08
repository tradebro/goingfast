# Going Fast

A Sanic based [TradingView](https://www.tradingview.com/gopro/?share_your_love=tista) alerts trader. Trading actions are run in the background to comply with TradingView's 3 seconds must reply and close connection rule.

## Endpoint

```
[POST] /webhook

+ Request (application/json)

        {
            "close": 11382.11,
            "indicator": "Bayesian SMI Oscillator - 13m",
            "exchange": "Coinbase",
            "pair": "BTCUSD",
            "action": "Long",
            "metadata": {
                "stop_limit_trigger_price": "11301.11",
                "rr": 1
            }
        }

+ Response 200
```

| Name | Description |
| :--- | :--- |
| `close` | Required, last close when alert is triggered |
| `indicator` | Required, the indicator used to trigger the alert, best practice to include timeframe |
| `exchange` | Required, exchange where the indicator is placed |
| `pair` | Required, pair monitored |
| `action` | Required, either be `Long` or `Short` |
| `metadata` | Optional |
| `metadata.stop_limit_trigger_price` | Optional, when this value is present, stop order will use this value |
| `metadata.rr` | Optional, when this value is present, TP price will be calculated using risk reward ratio supplied |

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

## Running

The easiest way to run is by using [Docker](https://hub.docker.com). To run locally a shell script is provided. Either way, I recommend setting `APP_DEBUG` to `1` to inspect your trades.

### Docker

```shell
$ docker pull tistaharahap/goingfast:latest
$ docker run -d --name fast -p 8080:8080 \
	-e APP_HOST="0.0.0.0" \
	-e APP_PORT="8080" \
	-e APP_DEBUG="1" \
	-e TELEGRAM_TOKEN="your_telegram_token" \
	-e TELEGRAM_CHAT_ID="your_chat_id" \
	-e STOP_DELTA="10" \
	-e TP_DELTA="50" \
	-e CAPITAL_IN_USD="10000" \
	-e API_KEY="" \
	-e API_SECRET="" \
	-e TRADER="bybit" \
	-e LEVERAGE="10" \
	tistaharahap/goingfast:latest
```

### Run Locally

```shell
$ git clone git@github.com:tradebro/goingfast.git
$ cd goingfast
$ python3 -m virtualenv env
$ . env/bin/activate
$ pip install -r requirements.txt
$ cp run-local.sh.example run-local.sh
$ chmod +x run-local.sh # At this point, edit the script with your own values
$ ./run-local.sh 
```

## Real World Usage

As per TradingView's recommendation, please whitelist only TradingView's IP addresses available in the link below:

[https://www.tradingview.com/support/solutions/43000529348-i-want-to-know-more-about-webhooks/](https://www.tradingview.com/support/solutions/43000529348-i-want-to-know-more-about-webhooks/)

A simple `nginx` rule like below.

```nginx
location / {
    allow 52.89.214.238;
    allow 34.212.75.30;
    allow 54.218.53.128;
    allow 52.32.178.7;
    deny all;
    proxy_pass http://127.0.0.1:8080;
}
```

This bot is limited in its capacity to do calculations. There is no technical analysis done, instead it processes values from indicators and executes based on provided values.

As long as the exchange is offering a reliable and transparent API (and its rate limit), the time it takes to accept requests, process and having an open position will take ~1 second. The flow is like below.

```
TradingView Chart => Add an Indicator => Create Alert => Alert Triggered => Webhook Triggered => Send Orders => Open Position
```

The closer the machine where you host the bot to TradingView and your exchange, the faster the response time is.

More about the reasoning for this bot's creation on my blog post below:

[Building A Bitcoin Trading Bot With Sanic](https://bango29.com/building-a-bitcoin-trading-bot-with-sanic/)
