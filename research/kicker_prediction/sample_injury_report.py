import nflreadpy as nfl
import pandas as pd

# Load 2024 injury data
injuries = nfl.load_injuries(seasons=[2024]).to_pandas()

print("="*100)
print("SAMPLE INJURY REPORT - Understanding the Data Structure")
print("="*100)

# Let's look at one team for one week to see the pattern
print("\nExample 1: Kansas City Chiefs - Week 18 (all injury reports)")
print("="*100)
kc_week18 = injuries[(injuries['team'] == 'KC') & (injuries['week'] == 18)]
kc_week18_sorted = kc_week18.sort_values('date_modified')

print(f"\nTotal reports: {len(kc_week18)}")
print("\nAll columns shown:")
print(kc_week18_sorted.to_string(index=False))

print("\n" + "="*100)
print("Example 2: Patrick Mahomes - All his injury reports in 2024")
print("="*100)
mahomes = injuries[injuries['full_name'] == 'Patrick Mahomes'].sort_values(['week', 'date_modified'])
print(mahomes[['week', 'date_modified', 'report_primary_injury', 'report_status',
               'practice_primary_injury', 'practice_status']].to_string(index=False))

print("\n" + "="*100)
print("Example 3: One player throughout a single week (to see daily updates)")
print("="*100)
# Let's find someone with multiple reports in one week
player_week_counts = injuries.groupby(['full_name', 'week']).size().reset_index(name='count')
multi_report = player_week_counts[player_week_counts['count'] > 1].head(1)

if len(multi_report) > 0:
    player = multi_report.iloc[0]['full_name']
    week = multi_report.iloc[0]['week']

    print(f"\nPlayer: {player}, Week: {week}")
    player_data = injuries[(injuries['full_name'] == player) & (injuries['week'] == week)].sort_values('date_modified')
    print(player_data[['date_modified', 'practice_primary_injury', 'practice_status',
                       'report_primary_injury', 'report_status']].to_string(index=False))

print("\n" + "="*100)
print("Example 4: Unique date_modified values for Week 1")
print("="*100)
week1 = injuries[injuries['week'] == 1]
unique_dates = week1['date_modified'].unique()
print(f"\nNumber of unique report dates in Week 1: {len(unique_dates)}")
print("\nFirst 10 dates:")
for date in sorted(unique_dates)[:10]:
    count = len(week1[week1['date_modified'] == date])
    print(f"  {date} - {count} reports")

print("\n" + "="*100)
print("Example 5: Same player, same week, different dates")
print("="*100)
# Group by player and week, filter for those with multiple date_modified entries
for idx, row in player_week_counts[player_week_counts['count'] > 2].head(3).iterrows():
    player = row['full_name']
    week = row['week']
    player_data = injuries[(injuries['full_name'] == player) & (injuries['week'] == week)].sort_values('date_modified')

    print(f"\n{player} - Week {week}:")
    print(player_data[['date_modified', 'practice_status', 'report_status']].to_string(index=False))

print("\n" + "="*100)
print("KEY INSIGHTS:")
print("="*100)
print("""
1. Each row = One injury report entry
2. date_modified = When the report was last updated/published
3. Multiple entries per player per week = Practice reports updated throughout the week
4. Typical pattern: Wed/Thu/Fri practice reports → Final game status
5. Practice status tracks daily: DNP → Limited → Full (or vice versa)
6. Report status = Final designation for the game (Out/Questionable/Doubtful)
""")
