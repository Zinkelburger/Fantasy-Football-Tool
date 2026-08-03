import nflreadpy as nfl

print("Available functions in nflreadpy:")
print("="*80)

# List all available load functions
funcs = [func for func in dir(nfl) if func.startswith('load_')]
for func in funcs:
    print(f"  - {func}")

print("\n" + "="*80)
print("Checking for injury data...")
print("="*80)

# Try to load injuries
try:
    print("\nTrying load_injuries for 2024...")
    injuries = nfl.load_injuries(seasons=[2024]).to_pandas()
    print(f"\nInjuries data found! Shape: {injuries.shape}")
    print(f"\nColumns ({len(injuries.columns)} total):")
    for col in injuries.columns:
        print(f"  - {col}")

    print(f"\n\nFirst 20 rows:")
    print("="*120)
    print(injuries.head(20).to_string())

    print(f"\n\nSample of injury statuses:")
    print("="*80)
    if 'report_status' in injuries.columns:
        print(injuries['report_status'].value_counts())

    print(f"\n\nSample of injury types:")
    print("="*80)
    if 'report_primary_injury' in injuries.columns:
        print(injuries['report_primary_injury'].value_counts().head(20))

except Exception as e:
    print(f"  Error loading injuries: {e}")

# Try 2025 injuries
try:
    print("\n" + "="*80)
    print("Trying load_injuries for 2025...")
    injuries_2025 = nfl.load_injuries(seasons=[2025]).to_pandas()
    print(f"\n2025 Injuries data found! Shape: {injuries_2025.shape}")
    print(f"\nFirst 10 rows:")
    print(injuries_2025.head(10).to_string())
except Exception as e:
    print(f"  2025 injuries not available yet: {e}")
