import statistics

class AnomalyFilter:
    def __init__(self, min_price=10, max_price=1000000000):
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
        valid_prices = [p for p in unit_prices if self.min_price <= p <= self.max_price]
        
        if not valid_prices:
            return [], 0

        # 3. Filter statistical outliers (if enough data)
        # Simple approach: Remove prices that are > 3 * median (to avoid skewing by massive prices)
        # or use Z-score if we want to be fancy. Let's stick to median for robustness.
        if len(valid_prices) >= 3:
            median = statistics.median(valid_prices)
            # Allow some variance, but cut off extreme values
            # e.g. if median is 1000, we accept up to 5000 (5x)
            upper_bound = median * 5 
            lower_bound = median / 5
            
            final_prices = [p for p in valid_prices if lower_bound <= p <= upper_bound]
        else:
            final_prices = valid_prices

        if not final_prices:
            return [], 0

        average = sum(final_prices) / len(final_prices)
        return final_prices, round(average)
