## Output Dataset

The script exports transaction-level Uniswap V3 swap data as a CSV file.

Each row represents one swap event recorded in the selected liquidity pool.


### Sample Output

Each row represents one Uniswap V3 swap event.

| utc_time | tx_hash | trader_address | sender_address | recipient_address | direction | exec_price | mid_price | impact_% | lp_fee_usd | gas_cost_usd | all_in_price |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2025-05-01 00:01:23 | `0x7f2a...9c81` | `0x91ab...4d72` | `0x68b3...fc45` | `0x91ab...4d72` | BUY | 1795.421300 | 1794.882100 | 0.0300 | 2.1035 | 8.3521 | 1797.109400 |
| 2025-05-01 00:03:41 | `0x36cd...e205` | `0x52f8...7b19` | `0x3fc9...ad31` | `0x52f8...7b19` | SELL | 1793.872500 | 1794.110200 | -0.0132 | 1.9864 | 6.9154 | 1792.489400 |
