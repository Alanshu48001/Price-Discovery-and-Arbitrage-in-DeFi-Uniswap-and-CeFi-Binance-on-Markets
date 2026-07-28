## Binance OHLCV Data Collection

This script downloads historical OHLCV candlestick data from Binance using the CCXT library.

The default configuration collects 1-minute ETH/USDC market data from 1 January 2025 to 1 July 2025.

### Output Data Format

The downloaded data are saved as a CSV file with the following columns:

| Column      | Description                            |
| ----------- | -------------------------------------- |
| `timestamp` | Opening time of the candlestick in UTC |
| `open`      | Opening price during the interval      |
| `high`      | Highest price during the interval      |
| `low`       | Lowest price during the interval       |
| `close`     | Closing price during the interval      |
| `volume`    | Trading volume during the interval     |

### Sample Output

```csv
timestamp,open,high,low,close,volume
2025-01-01 00:00:00+00:00,3330.93,3331.24,3329.32,3330.57,17.1206
2025-01-01 00:01:00+00:00,3331.58,3332.15,3330.82,3331.86,10.5409
2025-01-01 00:02:00+00:00,3333.15,3335.40,3333.15,3335.40,27.2397
2025-01-01 00:03:00+00:00,3335.41,3335.41,3331.59,3332.34,14.7232
2025-01-01 00:04:00+00:00,3332.91,3335.09,3332.68,3332.76,15.6296
```

### Changing the Trading Pair

The script can be used to download data for other tokens and trading pairs supported by Binance.

Change the `SYMBOL` parameter in the script:

```python
SYMBOL = "ETH/USDC"
```

For example:

```python
SYMBOL = "BTC/USDT"
```

```python
SYMBOL = "SOL/USDT"
```

```python
SYMBOL = "BNB/USDC"
```

The trading pair must exist on Binance and follow the CCXT symbol format:

```text
BASE_TOKEN/QUOTE_TOKEN
```

For example, in `ETH/USDC`, ETH is the base token and USDC is the quote token.

### Changing the Data Frequency

The candlestick frequency can be changed through the `TIMEFRAME` parameter:

```python
TIMEFRAME = "1m"
```

Common Binance timeframes include:

```text
1m, 3m, 5m, 15m, 30m
1h, 2h, 4h, 6h, 12h
1d, 3d, 1w, 1M
```

For example, to download hourly data:

```python
TIMEFRAME = "1h"
```

### Downloading More Historical Data

The amount of data collected is controlled by the start date and end date:

```python
START_DATE = "2025-01-01T00:00:00Z"
END_DATE = "2025-07-01T00:00:00Z"
```

To collect a longer historical period, change the date range:

```python
START_DATE = "2024-01-01T00:00:00Z"
END_DATE = "2025-07-01T00:00:00Z"
```

Binance limits the number of candlesticks returned by each API request. The script automatically sends repeated requests and combines the results until the full requested period has been downloaded.

The `LIMIT` parameter controls the maximum number of candlesticks requested per API call:

```python
LIMIT = 1_000
```

The script also pauses between requests to reduce the risk of reaching Binance API rate limits:

```python
REQUEST_INTERVAL_SECONDS = 0.5
```

For large datasets, the download may require many API requests. The final dataset is automatically sorted by timestamp and duplicate observations are removed.

### Example Configuration

The following configuration downloads 5-minute BTC/USDT data for the full year of 2025:

```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"

START_DATE = "2025-01-01T00:00:00Z"
END_DATE = "2026-01-01T00:00:00Z"
```

