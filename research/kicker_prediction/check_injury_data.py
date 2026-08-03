import nfl_data_py as nfl

print("Available functions in nfl_data_py:")
print("="*80)

# List all available import functions
funcs = [func for func in dir(nfl) if func.startswith('import_')]
for func in funcs:
    print(f"  - {func}")

print("\n" + "="*80)
print("Checking for injury-related data...")
print("="*80)

# Try to load weekly data which might have injury designations
try:
    print("\nTrying import_weekly_data (might have injury status)...")
    weekly = nfl.import_weekly_data([2025])
    print(f"Weekly data columns ({len(weekly.columns)} total):")

    # Look for injury-related columns
    injury_cols = [col for col in weekly.columns if any(word in col.lower() for word in ['injury', 'status', 'active', 'inactive'])]
    if injury_cols:
        print("  Injury-related columns found:")
        for col in injury_cols:
            print(f"    - {col}")
    else:
        print("  No injury-related columns found")
        print("\n  Sample columns:")
        for col in sorted(weekly.columns)[:20]:
            print(f"    - {col}")
except Exception as e:
    print(f"  Error: {e}")

# Try injuries data if it exists
try:
    print("\n" + "="*80)
    print("Trying import_injuries...")
    injuries = nfl.import_injuries([2025])
    print(f"\nInjuries data found! Shape: {injuries.shape}")
    print(f"Columns: {list(injuries.columns)}")
    print(f"\nFirst few rows:")
    print(injuries.head(10))
except Exception as e:
    print(f"  No injuries data available: {e}")
