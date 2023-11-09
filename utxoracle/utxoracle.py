#!/usr/bin/env python3

from pyln.client import Plugin
from pyln.client import LightningRpc
from math import log10
from bitcoin.core import CBlock
from io import BytesIO
import json

plugin = Plugin()

@plugin.method("utxoracle")
def utxoracle():
    """
    This plugin estimates the USD Bitcoin price for this past 144 blocks. It is dervied from the UTXOracle project, utxo.live/oracle
    """
    # We skip Parts 1 to 4 of UTXOracle
    lightning_rpc = LightningRpc("/home/ubuntu/.lightning/bitcoin/lightning-rpc")
   
    # Part 5) Build the container to hold the output amounts bell curve
    first_bin_value = -6
    last_bin_value = 6  #python -1 means last in list
    range_bin_values = last_bin_value - first_bin_value

    # create a list of output_bell_curve_bins and add zero sats as the first bin
    output_bell_curve_bins = [0.0] #a decimal tells python the list will contain decimals

    # calculate btc amounts of 200 samples in every 10x from 100 sats (1e-6 btc) to 100k (1e5) btc
    for exponent in range(-6,6): #python range uses 'less than' for the big number
        
        #add 200 bin_width increments in this 10x to the list
        for b in range(0,200):
            
            bin_value = 10 ** (exponent + b/200)
            output_bell_curve_bins.append(bin_value)

    # Create a list the same size as the bell curve to keep the count of the bins
    number_of_bins = len(output_bell_curve_bins)

    output_bell_curve_bin_counts = []
    for n in range(0,number_of_bins):
        output_bell_curve_bin_counts.append(float(0.0))

    # Part 6) Get all output amounts from the last 144 blocks
    getchaininfo_result = lightning_rpc.getchaininfo(815737)
    block_count_b = int(getchaininfo_result["blockcount"])
    latest_block = int(block_count_b)

    block_to_scan = latest_block - 143
    
    n = 0

    print("Estimating price for last day (144 blocks).")

    while block_to_scan <= latest_block:
        n = n + 1
        
        # status updates for scanning
        print("Scanning block",block_to_scan)
        print("{:.2%} complete".format(n/144))
        print("")
        
        block_response = lightning_rpc.getrawblockbyheight(block_to_scan)
        block_data = block_response['block']
        block = CBlock.stream_deserialize(BytesIO(bytes.fromhex(block_data)))

        #go through all the txs in the block which are stored in a list called 'tx'
        for tx in block.vtx:
            
            #go through all outputs in the tx
            for output in tx.vout:
                amount = float(output.nValue/100000000)

                #tiny and huge amounts aren't used by the USD price finder
                if 1e-6 < amount < 1e6:
                    #take the log
                    amount_log = log10(amount)
                    
                    #find the right output amount bin to increment
                    percent_in_range = (amount_log-first_bin_value)/range_bin_values
                    bin_number_est = int(percent_in_range * number_of_bins)
  
                    #search for the exact right bin (won't be less than)
                    while output_bell_curve_bins[bin_number_est] <= amount:
                        bin_number_est += 1
                    
                    bin_number = bin_number_est - 1
                    
                    #increment the output bin
                    output_bell_curve_bin_counts[bin_number] += 1.0   #+= means increment

        block_to_scan += 1
       
    # Part 7
    #remove ouputs below 1k sats
    for n in range(0,401):
        output_bell_curve_bin_counts[n]=0
        print("output_bell_curve_bin_counts[n]=0",output_bell_curve_bin_counts[n])

    #remove outputs above ten btc
    for n in range(1601,number_of_bins):
        output_bell_curve_bin_counts[n]=0 

    #create a list of round btc bin numbers
    round_btc_bins = [
    201,  # 1k sats
    401,  # 10k
    461,  # 20k
    496,  # 30k
    540,  # 50k
    601,  # 100k
    661,  # 200k
    696,  # 300k
    740,  # 500k
    801,  # 0.01 btc
    861,  # 0.02
    896,  # 0.03
    940,  # 0.04
    1001, # 0.1
    1061, # 0.2
    1096, # 0.3
    1140, # 0.5
    1201  # 1 btc
    ]

    #smooth over the round btc amounts
    for r in round_btc_bins:
        amount_above = output_bell_curve_bin_counts[r+1]
        amount_below = output_bell_curve_bin_counts[r-1]
        output_bell_curve_bin_counts[r] = .5*(amount_above+amount_below)

    #get the sum of the curve
    curve_sum = 0.0
    for n in range(201,1601):
        curve_sum += output_bell_curve_bin_counts[n]

    #normalize the curve by dividing by it's sum and removing extreme values
    for n in range(201,1601):
        output_bell_curve_bin_counts[n] /= curve_sum
        
        #remove extremes (the iterative process mentioned below found 0.008 to work)
        if output_bell_curve_bin_counts[n] > 0.008:
            output_bell_curve_bin_counts[n] = 0.008

    # Part 8)
    round_usd_stencil = []
    for n in range(0,number_of_bins):
        round_usd_stencil.append(0.0)

    # fill the round usd stencil with the values found by the process mentioned above
    round_usd_stencil[401] = 0.0005957955691168063     # $1
    round_usd_stencil[402] = 0.0004454790662303128     # (next one for tx/atm fees)
    round_usd_stencil[429] = 0.0001763099393598914     # $1.50
    round_usd_stencil[430] = 0.0001851801497144573
    round_usd_stencil[461] = 0.0006205616481885794     # $2
    round_usd_stencil[462] = 0.0005985696860584984
    round_usd_stencil[496] = 0.0006919505728046619     # $3
    round_usd_stencil[497] = 0.0008912933078342840
    round_usd_stencil[540] = 0.0009372916238804205     # $5
    round_usd_stencil[541] = 0.0017125522985034724     # (larger needed range for fees)
    round_usd_stencil[600] = 0.0021702347223143030
    round_usd_stencil[601] = 0.0037018622326411380     # $10
    round_usd_stencil[602] = 0.0027322168706743802
    round_usd_stencil[603] = 0.0016268322583097678     # (larger needed range for fees)
    round_usd_stencil[604] = 0.0012601953416497664
    round_usd_stencil[661] = 0.0041425242880295460     # $20
    round_usd_stencil[662] = 0.0039247767475640830
    round_usd_stencil[696] = 0.0032399441632017228     # $30
    round_usd_stencil[697] = 0.0037112959007355585
    round_usd_stencil[740] = 0.0049921908828370000     # $50
    round_usd_stencil[741] = 0.0070636869018197105
    round_usd_stencil[801] = 0.0080000000000000000     # $100
    round_usd_stencil[802] = 0.0065431388282424440     # (larger needed range for fees)
    round_usd_stencil[803] = 0.0044279509203361735
    round_usd_stencil[861] = 0.0046132440551747015     # $200
    round_usd_stencil[862] = 0.0043647851395531140
    round_usd_stencil[896] = 0.0031980892880846567     # $300
    round_usd_stencil[897] = 0.0034237641632481910
    round_usd_stencil[939] = 0.0025995335505435034     # $500
    round_usd_stencil[940] = 0.0032631930982226645     # (larger needed range for fees)
    round_usd_stencil[941] = 0.0042753262790881080
    round_usd_stencil[1001] =0.0037699501474772350     # $1,000
    round_usd_stencil[1002] =0.0030872891064215764     # (larger needed range for fees)
    round_usd_stencil[1003] =0.0023237040836798163
    round_usd_stencil[1061] =0.0023671764210889895     # $2,000
    round_usd_stencil[1062] =0.0020106877104798474
    round_usd_stencil[1140] =0.0009099214128654502     # $3,000
    round_usd_stencil[1141] =0.0012008546799361498
    round_usd_stencil[1201] =0.0007862586076341524     # $10,000
    round_usd_stencil[1202] =0.0006900048077192579

    ##############################################################################

    #  Part 9) Slide the stencil over the output bell curve to find the best fit

    ##############################################################################

    # This is the final step. We slide the stencil over the bell curve and see
    # where it fits the best. The best fit location and it's neighbor are used
    # in a weighted average to estimate the best fit USD price

    # set up scores for sliding the stencil
    best_slide       = 0
    best_slide_score = 0.0
    total_score      = 0.0
    number_of_scores = 0

    #upper and lower limits for sliding the stencil
    min_slide = -200
    max_slide = 200

    #slide the stencil and calculate slide score
    for slide in range(min_slide,max_slide):
    
        #shift the bell curve by the slide
        shifted_curve = output_bell_curve_bin_counts[201+slide:1401+slide]
        
        #score the shift by multiplying the curve by the stencil
        slide_score = 0.0
        for n in range(0,len(shifted_curve)):
            slide_score += shifted_curve[n]*round_usd_stencil[n+201]
        
        # increment total and number of scores
        total_score += slide_score
        number_of_scores += 1
        
        # see if this score is the best so far
        if slide_score > best_slide_score:
            best_slide_score = slide_score
            best_slide = slide

    # estimate the usd price of the best slide
    usd100_in_btc_best = output_bell_curve_bins[801+best_slide]
    btc_in_usd_best = 100/(usd100_in_btc_best)

    #find best slide neighbor up
    neighbor_up = output_bell_curve_bin_counts[201+best_slide+1:1401+best_slide+1]
    neighbor_up_score = 0.0
    for n in range(0,len(neighbor_up)):
        neighbor_up_score += neighbor_up[n]*round_usd_stencil[n+201]

    #find best slide neighbor down
    neighbor_down = output_bell_curve_bin_counts[201+best_slide-1:1401+best_slide-1]
    neighbor_down_score = 0.0
    for n in range(0,len(neighbor_down)):
        neighbor_down_score += neighbor_down[n]*round_usd_stencil[n+201]

    #get best neighbor
    best_neighbor = +1
    neighbor_score = neighbor_up_score
    if neighbor_down_score > neighbor_up_score:
        best_neighbor = -1
        neighbor_score = neighbor_down_score

    #get best neighbor usd price
    usd100_in_btc_2nd = output_bell_curve_bins[801+best_slide+best_neighbor]
    btc_in_usd_2nd = 100/(usd100_in_btc_2nd)

    #weight average the two usd price estimates
    avg_score = total_score/number_of_scores
    a1 = best_slide_score - avg_score
    a2 = abs(neighbor_score - avg_score)  #theoretically possible to be negative
    w1 = a1/(a1+a2)
    w2 = a2/(a1+a2)
    price_estimate = int(w1*btc_in_usd_best + w2*btc_in_usd_2nd)

    starting_block = latest_block - 143

    print("Estimated price for last 144 blocks = " + str(price_estimate))
    print("Starting block = " + str(starting_block))
    print("Ending block = " + str(latest_block))

    json_result = json.dumps({
        "last_x_blocks" : 144,
        "estimated_price": price_estimate,
        "starting_block": starting_block,
        "ending_block": latest_block
    })

    return json_result

plugin.run()
