"""
Download historical 1-minute ETH/USDC OHLCV data from Binance.

Data period:
    2025-01-01 00:00:00 UTC
    to
    2025-07-01 00:00:00 UTC

Output:
    data/binance_eth_usdc_1m_2025-01-01_2025-07-01.csv

Requirements:
    pip install ccxt pandas
"""

from pathlib import Path
import time

import ccxt
import pandas as pd


# =============================================================================
# Configuration
# =============================================================================

SYMBOL = "ETH/USDC"
TIMEFRAME = "1m"

START_DATE = "2025-01-01T00:00:00Z"
END_DATE = "2025-07-01T00:00:00Z"

# Binance generally returns up to 1,000 candles per request.
LIMIT = 1_000

# Pause between requests to reduce the risk of reaching the API rate limit.
REQUEST_INTERVAL_SECONDS = 0.5

OUTPUT_PATH = Path(
    "data/binance_eth_usdc_1m_2025-01-01_2025-07-01.csv"
)


def create_exchange() -> ccxt.binance:
    """
    Create a Binance exchange instance with CCXT rate limiting enabled.

    Returns
    -------
    ccxt.binance
        Configured Binance exchange instance.
    """
    return ccxt.binance(
        {
            "enableRateLimit": True,
        }
    )


def fetch_historical_ohlcv(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    limit: int = 1_000,
) -> list[list]:
    """
    Download historical OHLCV data using repeated API requests.

    CCXT returns OHLCV observations in the following format:

        [
            timestamp,
            open,
            high,
            low,
            close,
            volume,
        ]

    Parameters
    ----------
    exchange
        Configured CCXT Binance exchange instance.
    symbol
        Trading pair, for example ``ETH/USDC``.
    timeframe
        Candle frequency, for example ``1m``.
    start_date
        Start of the sample period in ISO 8601 UTC format.
    end_date
        End of the sample period in ISO 8601 UTC format.
    limit
        Maximum number of candles requested in each API call.

    Returns
    -------
    list[list]
        Combined OHLCV observations returned by Binance.
    """
    since = exchange.parse8601(start_date)
    end_time = exchange.parse8601(end_date)

    if since is None or end_time is None:
        raise ValueError("Start date and end date must use valid ISO 8601 format.")

    if since >= end_time:
        raise ValueError("The start date must be earlier than the end date.")

    all_ohlcv: list[list] = []

    while since < end_time:
        request_time = exchange.iso8601(since)
        print(f"Fetching data from {request_time}")

        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit,
            )

        except ccxt.RateLimitExceeded:
            print("Rate limit reached. Retrying after 10 seconds.")
            time.sleep(10)
            continue

        except ccxt.NetworkError as error:
            print(f"Network error: {error}. Retrying after 5 seconds.")
            time.sleep(5)
            continue

        except ccxt.ExchangeError as error:
            raise RuntimeError(
                f"Binance returned an exchange error: {error}"
            ) from error

        if not ohlcv:
            print("No additional observations were returned.")
            break

        all_ohlcv.extend(ohlcv)

        # Move the starting timestamp to the minute after the final candle.
        # This prevents the final candle from being downloaded twice.
        next_since = ohlcv[-1][0] + 60_000

        # Stop the loop if Binance does not advance the timestamp.
        if next_since <= since:
            print("Timestamp did not advance. Download stopped.")
            break

        since = next_since
        time.sleep(REQUEST_INTERVAL_SECONDS)

    return all_ohlcv


def prepare_dataframe(
    ohlcv: list[list],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Convert raw OHLCV observations into a cleaned pandas DataFrame.

    Parameters
    ----------
    ohlcv
        Raw OHLCV observations returned by CCXT.
    start_date
        Inclusive start of the sample period.
    end_date
        Exclusive end of the sample period.

    Returns
    -------
    pandas.DataFrame
        Cleaned OHLCV dataset sorted by timestamp.
    """
    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    df = pd.DataFrame(ohlcv, columns=columns)

    if df.empty:
        return df

    # Convert Binance millisecond timestamps to timezone-aware UTC timestamps.
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="ms",
        utc=True,
    )

    start_timestamp = pd.Timestamp(start_date)
    end_timestamp = pd.Timestamp(end_date)

    # Keep observations within the requested sample period.
    # The start timestamp is inclusive and the end timestamp is exclusive.
    df = df[
        (df["timestamp"] >= start_timestamp)
        & (df["timestamp"] < end_timestamp)
    ]

    # Remove duplicated candles and ensure chronological ordering.
    df = (
        df.drop_duplicates(subset="timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


def save_dataframe(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save the cleaned dataset as a CSV file.

    Parameters
    ----------
    df
        Cleaned OHLCV DataFrame.
    output_path
        Location of the output CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Saved {len(df):,} observations to:")
    print(output_path.resolve())


def main() -> None:
    """Run the Binance historical data collection pipeline."""
    exchange = create_exchange()

    print(f"Downloading {SYMBOL} {TIMEFRAME} data")
    print(f"Sample period: {START_DATE} to {END_DATE}")

    raw_ohlcv = fetch_historical_ohlcv(
        exchange=exchange,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        start_date=START_DATE,
        end_date=END_DATE,
        limit=LIMIT,
    )

    df = prepare_dataframe(
        ohlcv=raw_ohlcv,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    if df.empty:
        print("No data were downloaded for the requested period.")
        return

    print("\nFirst five observations:")
    print(df.head())

    print("\nLast five observations:")
    print(df.tail())

    print(f"\nTotal observations: {len(df):,}")
    print(f"First timestamp: {df['timestamp'].min()}")
    print(f"Last timestamp: {df['timestamp'].max()}")

    save_dataframe(df, OUTPUT_PATH)


if __name__ == "__main__":
    main()