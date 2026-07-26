#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Uniswap V3 Transaction-Level Swap Data Extraction
and All-In Price Calculation
==================================================

This script retrieves transaction-level swap data from a selected
Uniswap V3 liquidity pool through The Graph Subgraph.

Output columns:
    utc_time
    direction
    exec_price
    mid_price
    impact_%
    lp_fee_usd
    gas_cost_usd
    all_in_price

The execution price is calculated from the actual token amounts transferred
during each swap. These token amounts already reflect the Uniswap pool fee.

Therefore, the pool fee is reported separately for analytical purposes but is
not added to or deducted from the all-in price again.

All-in price calculation:

    BUY:
        (USDC paid + gas cost) / WETH received

    SELL:
        (USDC received - gas cost) / WETH sold

All data are retrieved from the Uniswap V3 Subgraph.
This script does not query Etherscan directly.
"""

import requests
import statistics
import csv
import time

from decimal import Decimal, getcontext
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

# Replace this placeholder with your own The Graph API key.
#
# Do not upload a real API key to a public GitHub repository.
#
# Large historical data requests may consume the free request quota.
# If the active key reaches its usage limit, it may be replaced with another
# API key that you are authorized to use, subject to The Graph's account
# policies and terms of service.
#
# Example:
# API_KEY = "YOUR_THE_GRAPH_API_KEY"
API_KEY = "YOUR_THE_GRAPH_API_KEY"


# Uniswap V3 pool address to track.
#
# The current address represents the WETH/USDC 0.05% pool:
# 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640
#
# Replace this address to retrieve transactions from another Uniswap V3 pool.
#
# Important:
# This script assumes token0 is USDC and token1 is WETH.
# A pool with different tokens, token ordering, decimals, or fee tier may
# require changes to the price conversion and transaction-direction logic.
POOL = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640".lower()


# The Graph endpoint for the Uniswap V3 Subgraph.
URL = (
    f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/"
    f"5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
)


# Pool fee tier.
#
# 0.0005 represents a 0.05% Uniswap V3 pool fee.
# Change this value when using a pool with another fee tier.
FEE_TIER = Decimal("0.0005")


# Maximum number of swaps retrieved in each GraphQL request.
BATCH = 1_000


# Fallback gas values are used when transaction-level gas information
# is missing from the Subgraph response.
FALLBACK_GAS_GWEI = 30
FALLBACK_GAS_USED = 180_000


# Name of the exported CSV file.
CSV_FILE = "weth_usdc_2025-05-01_to_2025-05-02.csv"


# ============================================================
# DATA COLLECTION PERIOD
# ============================================================

# Set the data collection period in UTC.
#
# Change the year, month, day, hour, and minute values below to retrieve
# swaps from a different time period.
#
# START_TS is inclusive.
# END_TS is exclusive.
#
# The example below retrieves swaps from:
#
# 2025-05-01 00:00:00 UTC
# to
# 2025-05-02 00:00:00 UTC
#
# Transactions occurring exactly at END_TS are not included.

START_TS = int(
    datetime(
        2025,
        5,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    ).timestamp()
)

END_TS = int(
    datetime(
        2025,
        5,
        2,
        0,
        0,
        tzinfo=timezone.utc,
    ).timestamp()
)


# Example for retrieving the entire month of May 2025:
#
# START_TS = int(
#     datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc).timestamp()
# )
#
# END_TS = int(
#     datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc).timestamp()
# )


# Set high decimal precision for Uniswap price calculations.
getcontext().prec = 60

# Q96 is used to convert Uniswap V3 sqrtPriceX96 values.
Q96 = Decimal(2) ** 96


# ============================================================
# 1. RETRIEVE POOL TOKEN DECIMALS
# ============================================================

meta_q = f"""
{{
    pool(id: "{POOL}") {{
        token0 {{
            decimals
        }}
        token1 {{
            decimals
        }}
    }}
}}
"""

meta_response = requests.post(
    URL,
    json={"query": meta_q},
)

p = meta_response.json()["data"]["pool"]

dec0 = int(p["token0"]["decimals"])
dec1 = int(p["token1"]["decimals"])


def weth_per_usdc(sqrt_str: str) -> Decimal:
    """
    Convert a Uniswap V3 sqrtPriceX96 value into WETH per USDC.

    This calculation assumes token0 is USDC and token1 is WETH.
    """

    sqrt_price = Decimal(sqrt_str) / Q96

    return (
        sqrt_price**2
        * Decimal(10) ** (dec0 - dec1)
    )


# ============================================================
# 2. DOWNLOAD SWAP TRANSACTIONS
# ============================================================

rows = []
skip = 0

print("Downloading swaps...")


while True:

    query = f"""
    {{
        swaps(
            first: {BATCH},
            skip: {skip},
            orderBy: timestamp,
            orderDirection: asc,
            where: {{
                pool: "{POOL}",
                timestamp_gte: {START_TS}
            }}
        ) {{
            timestamp
            sqrtPriceX96
            amount0
            amount1

            transaction {{
                gasPrice
                gasUsed
            }}
        }}
    }}
    """

    response = requests.post(
        URL,
        json={"query": query},
    )

    batch = response.json()["data"]["swaps"]

    if not batch:
        break

    for swap in batch:

        timestamp = int(swap["timestamp"])

        # Stop collecting when the transaction reaches the exclusive end time.
        if timestamp >= END_TS:
            batch = []
            break

        rows.append(swap)

    if len(batch) < BATCH:
        break

    skip += BATCH

    # Add a short delay between requests to reduce API request pressure.
    time.sleep(0.2)


print(f"Total swaps fetched: {len(rows):,}")


# ============================================================
# 3. PREPARE GAS-DATA FALLBACK VALUES
# ============================================================

# Collect all valid transaction-level gas prices.
gas_price_values = [
    int(row["transaction"]["gasPrice"])
    for row in rows
    if row["transaction"]["gasPrice"] not in (None, "0")
]


# Collect all valid transaction-level gas-used values.
gas_used_values = [
    int(row["transaction"]["gasUsed"])
    for row in rows
    if row["transaction"]["gasUsed"] not in (None, "0")
]


# Use the median observed gas price when available.
# Otherwise, use the predefined fallback gas price.
gas_price_fallback = (
    Decimal(statistics.median(gas_price_values))
    if gas_price_values
    else Decimal(FALLBACK_GAS_GWEI) * Decimal(1_000_000_000)
)


# Use the median observed gas-used value when available.
# Otherwise, use the predefined fallback value.
gas_used_fallback = (
    Decimal(statistics.median(gas_used_values))
    if gas_used_values
    else Decimal(FALLBACK_GAS_USED)
)


# ============================================================
# 4. CALCULATE TRANSACTION-LEVEL FIELDS
# ============================================================

output = []


for swap in rows:

    # Each swap retains its own on-chain timestamp.
    timestamp = int(swap["timestamp"])

    # amount0 and amount1 represent changes in the pool's token balances.
    amount0 = Decimal(swap["amount0"])
    amount1 = Decimal(swap["amount1"])


    if amount0 > 0 and amount1 < 0:

        # BUY:
        # The trader sends USDC to the pool and receives WETH.

        direction = "BUY"

        usdc_in = amount0
        weth_out = -amount1

        # The transaction-level execution price already reflects the pool fee
        # because usdc_in represents the total amount transferred to the pool.
        execution_price = usdc_in / weth_out

        # Estimate the Uniswap pool fee for reporting purposes.
        #
        # This fee is already included in the transaction input amount.
        # It must not be added to the all-in price again.
        lp_fee_usd = usdc_in * FEE_TIER

        base_usdc = usdc_in
        weth_amount = weth_out


    elif amount0 < 0 and amount1 > 0:

        # SELL:
        # The trader sends WETH to the pool and receives USDC.

        direction = "SELL"

        weth_in = amount1
        usdc_out = -amount0

        # The transaction-level execution price already reflects the pool fee
        # because weth_in represents the total amount transferred to the pool.
        execution_price = usdc_out / weth_in

        # Estimate the pool fee charged in WETH.
        lp_fee_weth = weth_in * FEE_TIER

        # Convert the estimated WETH fee into USD.
        #
        # This value is reported separately and is not deducted from the
        # all-in price again.
        lp_fee_usd = lp_fee_weth * execution_price

        base_usdc = usdc_out
        weth_amount = weth_in


    else:

        # Skip unexpected token-flow patterns.
        continue


    # Convert sqrtPriceX96 into the pool's marginal USDC-per-WETH price.
    mid_price = Decimal(1) / weth_per_usdc(
        swap["sqrtPriceX96"]
    )


    # Measure the percentage difference between the transaction execution
    # price and the pool's marginal price.
    price_impact_pct = (
        (execution_price - mid_price)
        / mid_price
        * Decimal(100)
    )


    # Use transaction-level gas information when available.
    #
    # If either value is missing or zero, use the median fallback value.
    gas_price = (
        Decimal(swap["transaction"]["gasPrice"] or 0)
        or gas_price_fallback
    )

    gas_used = (
        Decimal(swap["transaction"]["gasUsed"] or 0)
        or gas_used_fallback
    )


    # Convert the Ethereum gas cost into USD.
    #
    # gasPrice is measured in wei.
    # 1 ETH equals 10^18 wei.
    gas_cost_usd = (
        gas_price
        * gas_used
        / Decimal(10**18)
        * mid_price
    )


    # The execution price already includes the Uniswap pool fee.
    #
    # Therefore, only the gas cost is added or deducted when calculating
    # the final all-in price.
    if direction == "BUY":

        all_in_usdc = (
            base_usdc
            + gas_cost_usd
        )

    else:

        all_in_usdc = (
            base_usdc
            - gas_cost_usd
        )


    all_in_price = (
        all_in_usdc
        / weth_amount
    )


    output.append(
        {
            "utc_time": datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc,
            ).strftime("%Y-%m-%d %H:%M:%S"),

            "direction": direction,

            "exec_price": (
                f"{execution_price:.6f}"
            ),

            "mid_price": (
                f"{mid_price:.6f}"
            ),

            "impact_%": (
                f"{price_impact_pct:.4f}"
            ),

            "lp_fee_usd": (
                f"{lp_fee_usd:.4f}"
            ),

            "gas_cost_usd": (
                f"{gas_cost_usd:.4f}"
            ),

            "all_in_price": (
                f"{all_in_price:.6f}"
            ),
        }
    )


# ============================================================
# 5. EXPORT RESULTS TO CSV
# ============================================================

if not output:

    print(
        "No swap transactions were found within the selected time period."
    )

else:

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=output[0].keys(),
        )

        writer.writeheader()
        writer.writerows(output)


    print(
        f"Done: {CSV_FILE} "
        f"({len(output):,} rows)"
    )
