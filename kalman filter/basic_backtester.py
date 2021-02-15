import pandas as pd
import numpy as np

class BasicBacktester():

    def calculate_summary_statistics(self, scores):
        summary_statistics = {}
        
        summary_statistics['gross_pnl_mean'] = round(scores['gross_pnl'].mean(), 2)
        summary_statistics['net_pnl_mean'] = round(scores['net_pnl'].mean(), 2)
        summary_statistics['gross_pnl_sum'] = round(scores['gross_pnl'].sum(), 2)
        summary_statistics['net_pnl_sum'] = round(scores['net_pnl'].sum(), 2)
        summary_statistics['gain_to_pain'] = round(scores[scores['net_pnl'] > 0]['net_pnl'].sum() / abs(scores[scores['net_pnl'] < 0]['net_pnl'].sum()), 2)
        summary_statistics['adjusted_expectancy'] = round(scores['net_pnl'].mean() / abs(scores[scores['net_pnl'] < 0]['net_pnl'].mean()), 2)
        
        return summary_statistics

    def single_asset_scorer(self, signals_df, security_name, security_leverage, market_friction):

        scores = pd.DataFrame({})
        
        score = {
                'datetime': 0,
                'positions': 0,
                'price': 0,
                'pnl': 0,
                'market_friction': 0
                }
        
        # data structures for orders
        entry_price_list = []
        entry_qty_list = []
        
        # going through the signals_df
        for current_time, signal in signals_df.iterrows():
        
            if signal[f'Δ{security_name}'] != 0:
                print(f'The signal is {signal}')
            
            entry_price_list, entry_qty_list, score = calculate_pnl(security_name, signal, score, entry_price_list, entry_qty_list)
            
            score['datetime'] = current_time
            score['positions'] = sum(entry_qty_list)
            score['price'] = np.mean(entry_price_list) if entry_price_list else 0
            score['market_friction'] = abs(signal[f'Δ{security_name}']) * -market_friction
            scores = scores.append(score, ignore_index=True)
        
        # if there are any left over qtys
        if entry_price_list:
            score['datetime'] = current_time
            score['pnl'] = (signals_df.iloc[-1][f'{security_name}_close'] - np.mean(entry_price_list))*sum(entry_qty_list)
            score['positions'] = 0
            score['price'] = 0
            scores = scores.append(score, ignore_index=True)
            
        scores = scores.set_index('datetime')
        scores = scores.resample('1D').sum()
        scores = scores.drop('price', axis=1)
        scores['gross_pnl'] = scores['pnl']*security_leverage
        scores['net_pnl'] = scores['gross_pnl'] + scores['market_friction']
        
        return scores
                    
def calculate_pnl(security_name, signal, score, entry_price_list, entry_qty_list):
    # what is the current net position before modifications
    pnl_change = 0
    net_position = sum(entry_qty_list)

    # modifications to be made this minute
    change_in_position = signal[f'Δ{security_name}']

    # there is a position modification
    if change_in_position != 0:
        # and the position is in the same net direction
        if net_position*change_in_position >= 0:
            # just add the position to the position queue
            entry_price_list.append(signal[f'{security_name}_close'])
            entry_qty_list.append(change_in_position)

        # if the position is not in the same net direction
        elif net_position*change_in_position < 0:

            working_change_in_position = change_in_position
            quantity_list_empty = not entry_qty_list

            # check if we are done making position modifications
            while abs(working_change_in_position) > 0:

                # if there is no more existing positions to modify
                if quantity_list_empty:
                    # then we just add the remainder of the working positions
                    entry_qty_list.append(working_change_in_position)
                    entry_price_list.append(signal[f'{security_name}_close'])
                    
                    # there is no more position modifications
                    working_change_in_position = 0
                    break

                # if we still have existing positions to modify
                if not quantity_list_empty:
                    # check if the current working position is at least one slot
                    if abs(working_change_in_position) >= abs(entry_qty_list[0]):

                        # reduce working changes
                        working_change_in_position += entry_qty_list[0]
                        
                        if entry_price_list:
                            entry_price_popped = entry_price_list.pop(0)
                            entry_qty_popped = entry_qty_list.pop(0)

                        # calculate pnl_change
                        pnl_change += (signal[f'{security_name}_close'] - entry_price_popped)*entry_qty_popped

                        # check if we still ahve existing positions to modify
                        quantity_list_empty = not entry_qty_list

                    # if current working positions is less than one slot
                    elif abs(working_change_in_position) < abs(entry_qty_list[0]):
                        # we reduce the first slot by the working_change_in_positions
                        entry_qty_list[0] = entry_qty_list[0] + working_change_in_position
                        
                        pnl_change += (signal[f'{security_name}_close'] - entry_price_list[0])*(-working_change_in_position)

                        # there is no more position modifications
                        working_change_in_position = 0
                        break

    score['pnl'] = pnl_change
                
    return entry_price_list, entry_qty_list, score