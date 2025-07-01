def calculate_pivot_points(high, low, close):
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {
        'Pivot': pivot,
        'R1': r1,
        'S1': s1,
        'R2': r2,
        'S2': s2,
        'R3': r3,
        'S3': s3
    }

def check_pivot_crossing_test(stock, price, pivot_levels, threshold=0.01):
    """Test version of the pivot crossing logic"""
    print(f"🔍 Testing pivot crossing for {stock} at ${price:.2f}")
    print(f"📊 Pivot levels: {pivot_levels}")
    
    # Find the closest pivot level that the price is approaching
    closest_level = None
    closest_distance = float('inf')
    approaching_direction = None
    
    for level_name, level_value in pivot_levels.items():
        distance = abs(price - level_value)
        print(f"📏 {stock} ${price:.2f} vs {level_name} ${level_value:.2f} = distance ${distance:.2f} (threshold: ${threshold})")
        
        # Only consider levels within threshold
        if distance < threshold:
            # Determine if price is approaching from above or below
            if price > level_value:
                direction = "down"  # Price is above level, approaching from above
            else:
                direction = "up"    # Price is below level, approaching from below
            
            print(f"🎯 {stock} at ${price:.2f} is approaching {level_name} ${level_value:.2f} from {direction}")
            
            # Keep track of the closest level within threshold
            if distance < closest_distance:
                closest_distance = distance
                closest_level = level_name
                approaching_direction = direction
    
    # If we found a level to alert on
    if closest_level:
        level_value = pivot_levels[closest_level]
        print(f"✅ RESULT: {stock} at ${price:.2f} approaching {closest_level} ${level_value:.2f} from {approaching_direction}")
        return closest_level, approaching_direction
    else:
        print(f"❌ No pivot level crossings detected for {stock} at ${price:.2f}")
        return None, None

# Test with LABU scenario
print("🧪 Testing LABU scenario...")
# Example pivot levels (you can replace with actual LABU levels)
labu_pivots = {
    'Pivot': 60.00,
    'R1': 58.50,
    'S1': 61.50,
    'R2': 57.00,
    'S2': 63.00,
    'R3': 55.50,
    'S3': 64.50
}

# Test price approaching R1
test_price = 58.21
result_level, result_direction = check_pivot_crossing_test("LABU", test_price, labu_pivots, threshold=0.3)

print(f"\n📋 Test Summary:")
print(f"   Price: ${test_price:.2f}")
print(f"   Expected: R1 (closest level)")
print(f"   Actual: {result_level}")
print(f"   Direction: {result_direction}")
print(f"   ✅ Correct: {'Yes' if result_level == 'R1' else 'No'}") 