# UTXOracle Plugin

## Plugin Method: `utxoracle`

The `utxoracle` method computes an estimated USD price of Bitcoin based on the outputs within the last 144 blocks on the blockchain.

## Dependencies

- Python 3
- `pyln-client`
- `bitcoin.core`
- `io`
- `json`
- `math`

## Usage

To use the UTXOracle plugin, you need to have a running instance of Core Lightning running.

Invoke the plugin with:


```lightningd --plugin=/path/to/utxoracle.py```


### How It Works

#### Build the Container for Output Amounts Bell Curve:
- Establishes a range for the bell curve bins to contain output amounts.
- Fills the bell curve bins with calculated Bitcoin amounts.

#### Get All Output Amounts from the Last 144 Blocks:
- Fetches the current block count and sets the range to the last 144 blocks for analysis.

#### Process and Categorize Output Amounts:
- Scans each block within the specified range.
- Categorizes every transaction output into the corresponding bell curve bin.

#### Normalize the Curve and Remove Extremes:
- Removes output amounts below 1k sats and above ten btc from the analysis.
- Smoothens the curve by averaging the counts around round btc amounts.

#### Slide the Stencil Over the Output Bell Curve:
- Slides a predefined stencil over the bell curve to find the best fit.
- Uses a weighted average to estimate the best fit USD price.

### Output

The plugin returns a JSON object with the following structure:

```json
{
    "last_x_blocks": 144,
    "estimated_price": "<price_estimate>",
    "starting_block": "<starting_block>",
    "ending_block": "<latest_block>"
}
