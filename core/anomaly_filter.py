import statistics

class AnomalyFilter:
    def __init__(self, min_price=0, max_price=1000000000):
        self.min_price = min_price
        self.max_price = max_price

    def filter_prices(self, prices):
        """
        Filters a list of prices to remove anomalies.
        Returns a tuple (filtered_prices, average_price).
        """
        if not prices:
            return [], 0

        # 1. Convert raw prices (x1, x10, x100, x1000) to unit prices
        unit_prices = []
        for i in range(0, len(prices), 4):
            chunk = prices[i:i+4]
            # Pad chunk with 0 if incomplete
            while len(chunk) < 4:
                chunk.append(0)
                
            p1, p10, p100, p1000 = chunk
            
            if p1 > 0: unit_prices.append(p1)
            if p10 > 0: unit_prices.append(p10 / 10)
            if p100 > 0: unit_prices.append(p100 / 100)
            if p1000 > 0: unit_prices.append(p1000 / 1000)

        if not unit_prices:
            return [], 0

        # 2. Filter absolute anomalies (too low / too high)
        # Note: min_price should be 0 or very low to accept unit prices < 1 (e.g. 100 items for 10k -> 0.1u)
        # Also filter out MAX_INT values (2147483647) which are often noise
        valid_prices = [
            p for p in unit_prices 
            if self.min_price <= p <= self.max_price and p < 2000000000
        ]
        
        if not valid_prices:
            return [], 0

        # 3. Filter statistical outliers
        if len(valid_prices) >= 3:
            median = statistics.median(valid_prices)
            # Allow some variance, but cut off extreme values
            # e.g. if median is 1000, we accept up to 5000 (5x)
            upper_bound = median * 5 
            lower_bound = median / 5
            
            final_prices = [p for p in valid_prices if lower_bound <= p <= upper_bound]
        elif len(valid_prices) == 2:
            # If we only have 2 prices, check for massive disparity
            p1, p2 = sorted(valid_prices)
            if p1 > 0 and p2 > p1 * 10: # If one is 10x bigger than the other
                # Assume the smaller one is the "real" price (often people put 1 item at crazy price)
                final_prices = [p1]
            else:
                final_prices = valid_prices
        else:
            final_prices = valid_prices

        if not final_prices:
            return [], 0

        average = sum(final_prices) / len(final_prices)
        
        # Round to 2 decimal places for unit prices < 1, otherwise integer is fine?
        # The user expects integer or float? The DB stores numeric.
        # But the return type hint suggests round(average) -> int.
        # If average is 0.5, round is 0 or 1.
        # Let's keep round() for now as per original code, but maybe it should be improved later.
        # Actually, if unit price is 0.1, round is 0. That's bad.
        # But for now let's stick to fixing the outlier issue.
        
        return final_prices, round(average, 2) if average < 10 else round(average)
