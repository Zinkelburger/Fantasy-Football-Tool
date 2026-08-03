import nflreadpy as nfl
import pandas as pd

print("Step-by-step guide to accessing injury data with nflreadpy:")
print("="*80)

print("\n1. Import the library:")
print("   import nflreadpy as nfl")

print("\n2. Load injury data for a specific season (e.g., 2024):")
print("   injuries = nfl.load_injuries(seasons=[2024])")

print("\n3. Convert to pandas DataFrame:")
print("   df = injuries.to_pandas()")

print("\n" + "="*80)
print("Let's do it live:")
print("="*80)

# Load injuries for 2024
print("\nLoading injuries for 2024...")
injuries = nfl.load_injuries(seasons=[2024])

print(f"Type of injuries object: {type(injuries)}")
print(f"Injuries is a Polars DataFrame: {injuries}")

# Convert to pandas
print("\nConverting to pandas...")
df = injuries.to_pandas()

print(f"Type after conversion: {type(df)}")
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

print("\n" + "="*80)
print("Example 1: Get all injuries for Week 1")
print("="*80)
week1 = df[df['week'] == 1]
print(f"\nWeek 1 injuries: {len(week1)} reports")
print("\nFirst 5:")
print(week1[['team', 'full_name', 'position', 'report_primary_injury', 'report_status']].head().to_string(index=False))

print("\n" + "="*80)
print("Example 2: Get all injuries for a specific team (e.g., KC)")
print("="*80)
kc_injuries = df[df['team'] == 'KC']
print(f"\nKC injuries in 2024: {len(kc_injuries)} reports")
print("\nFirst 10:")
print(kc_injuries[['week', 'full_name', 'position', 'report_primary_injury', 'report_status']].head(10).to_string(index=False))

print("\n" + "="*80)
print("Example 3: Get all players marked as 'Out' in a specific week")
print("="*80)
week5_out = df[(df['week'] == 5) & (df['report_status'] == 'Out')]
print(f"\nPlayers out in Week 5: {len(week5_out)}")
print("\nFirst 10:")
print(week5_out[['team', 'full_name', 'position', 'report_primary_injury']].head(10).to_string(index=False))

print("\n" + "="*80)
print("Example 4: Track a specific player's injuries throughout the season")
print("="*80)
# Let's pick someone who was likely injured
player_name = "Patrick Mahomes"
player_injuries = df[df['full_name'].str.contains(player_name, na=False)]
if len(player_injuries) > 0:
    print(f"\n{player_name} injury reports:")
    print(player_injuries[['week', 'report_primary_injury', 'report_status', 'practice_status']].to_string(index=False))
else:
    print(f"\n{player_name} had no injury reports in 2024")

print("\n" + "="*80)
print("Example 5: Load multiple seasons at once")
print("="*80)
print("\nLoading 2023 and 2024...")
multi_season = nfl.load_injuries(seasons=[2023, 2024]).to_pandas()
print(f"Total injury reports across 2023-2024: {len(multi_season)}")
print(f"2023: {len(multi_season[multi_season['season'] == 2023])}")
print(f"2024: {len(multi_season[multi_season['season'] == 2024])}")

print("\n" + "="*80)
print("SUMMARY: How to access injury data")
print("="*80)
print("""
1. Install: pip install nflreadpy

2. Basic usage:
   import nflreadpy as nfl
   injuries = nfl.load_injuries(seasons=[2024]).to_pandas()

3. Filter by:
   - Week:   injuries[injuries['week'] == 5]
   - Team:   injuries[injuries['team'] == 'KC']
   - Status: injuries[injuries['report_status'] == 'Out']
   - Player: injuries[injuries['full_name'] == 'Player Name']

4. Available columns:
   - season, game_type, team, week
   - gsis_id, position, full_name, first_name, last_name
   - report_primary_injury, report_secondary_injury, report_status
   - practice_primary_injury, practice_secondary_injury, practice_status
   - date_modified
""")
