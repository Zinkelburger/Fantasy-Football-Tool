import pandas as pd
import nfl_data_py as nfl

# Load 2025 play-by-play data
print("Loading 2025 NFL data...")
pbp = nfl.import_pbp_data([2025])

print(f"\nTotal columns: {len(pbp.columns)}")
print("\nAll available columns:")
print("="*80)

# Print all columns, sorted alphabetically
for i, col in enumerate(sorted(pbp.columns), 1):
    print(f"{i:3d}. {col}")

# Search for any injury-related columns
print("\n" + "="*80)
print("Columns containing 'injury' or 'hurt':")
injury_cols = [col for col in pbp.columns if 'injury' in col.lower() or 'hurt' in col.lower()]
if injury_cols:
    for col in injury_cols:
        print(f"  - {col}")
else:
    print("  None found")

# Let's also check for 'out', 'inactive', 'questionable' etc
print("\nColumns containing 'out', 'inactive', or 'status':")
status_cols = [col for col in pbp.columns if any(word in col.lower() for word in ['out', 'inactive', 'status', 'available'])]
if status_cols:
    for col in status_cols:
        print(f"  - {col}")
else:
    print("  None found")
