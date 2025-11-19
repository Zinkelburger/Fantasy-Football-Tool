import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os

# ==========================================
# CONFIGURATION
# ==========================================
START_YEAR = 2021
END_YEAR = 2025
WEEKS = range(1, 19) # Weeks 1-18
OUTPUT_FILE = 'nfl_injuries_2021_2025.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Referer': 'https://www.footballdb.com/'
}

def scrape_week(year, week):
    """Scrapes a single week of data from FootballDB"""
    url = f"https://www.footballdb.com/transactions/injuries.html?yr={year}&wk={week}&type=reg"
    print(f"   Processing {year} Week {week}...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"   ❌ Error fetching URL: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    week_data = []
    
    # FootballDB structure: 
    # <div class="teamsectlabel">Team Name</div>
    # <div class="divtable">...rows...</div>
    
    # We find all team labels, then look for the adjacent table
    team_labels = soup.find_all('div', class_='teamsectlabel')
    
    if not team_labels:
        print("   ⚠️ No data found (page might be empty or structure changed)")
        return []

    for label in team_labels:
        team_name = label.get_text(strip=True)
        
        # Find the next sibling that is a table
        # The HTML structure shows the table comes immediately after the label
        table = label.find_next_sibling('div', class_='divtable')
        
        if not table:
            continue
            
        # --- Parse Header for Practice Dates ---
        # The headers vary (Wed/Thu/Fri vs Mon/Tue/Wed etc.)
        header_row = table.find('div', class_='thead')
        if not header_row:
            continue
            
        headers = header_row.find_all('div', class_='th')
        # Expected indices: 0=Player, 1=Injury, 2=Day1, 3=Day2, 4=Day3, 5=Status
        # We grab texts from indices 2, 3, 4 to get the dates (e.g., "Wed 09/03")
        if len(headers) >= 6:
            day_1_label = headers[2].get_text(strip=True)
            day_2_label = headers[3].get_text(strip=True)
            day_3_label = headers[4].get_text(strip=True)
        else:
            day_1_label, day_2_label, day_3_label = "Day 1", "Day 2", "Day 3"

        # --- Parse Rows ---
        rows = table.find_all('div', class_='tr')
        
        for row in rows:
            cells = row.find_all('div', class_='td')
            if len(cells) < 6:
                continue
                
            # Cell 0: Player Name & Position
            # Contains multiple spans for mobile/desktop. We want desktop: 'd-none d-xl-inline'
            player_cell = cells[0]
            desktop_span = player_cell.find('span', class_='d-none d-xl-inline')
            
            if desktop_span:
                # Format: <a ...>Player Name</a> (POS)
                player_text = desktop_span.get_text(strip=True)
                # Attempt to split Name and Position
                if '(' in player_text:
                    player_name = player_text.split('(')[0].strip()
                    position = player_text.split('(')[1].replace(')', '').strip()
                else:
                    player_name = player_text
                    position = "Unknown"
            else:
                # Fallback if desktop span missing
                player_name = player_cell.get_text(strip=True)
                position = "Unknown"

            # Cell 1: Injury Type
            injury = cells[1].get_text(strip=True)
            
            # Cell 2, 3, 4: Practice Statuses
            practice_1 = cells[2].get_text(strip=True)
            practice_2 = cells[3].get_text(strip=True)
            practice_3 = cells[4].get_text(strip=True)
            
            # Cell 5: Game Status
            # Sometimes format is "(09/05) Out vs Team" or just "Out"
            game_status_raw = cells[5].get_text(strip=True)
            # Clean up the status (remove date/opponent if present)
            # Example: "(09/05) Questionable vs Det" -> "Questionable"
            game_status = game_status_raw
            if ')' in game_status:
                # Split by ')' and take the part after, then maybe split by 'vs' or '@'
                parts = game_status.split(')')
                if len(parts) > 1:
                    status_part = parts[1].strip()
                    # Remove "vs Team" or "@ Team"
                    status_clean = status_part.split(' vs ')[0].split(' @ ')[0].strip()
                    game_status = status_clean

            week_data.append({
                'season': year,
                'week': week,
                'team': team_name,
                'player': player_name,
                'position': position,
                'injury': injury,
                'day_1_date': day_1_label,
                'day_1_status': practice_1,
                'day_2_date': day_2_label,
                'day_2_status': practice_2,
                'day_3_date': day_3_label,
                'day_3_status': practice_3,
                'game_status': game_status
            })
            
    return week_data

def main():
    all_data = []
    
    print(f"🚀 Starting scrape for years {START_YEAR}-{END_YEAR}...")
    
    for year in range(START_YEAR, END_YEAR + 1):
        for week in WEEKS:
            # Check if we are in the future (simple check for 2025)
            # You might want to add logic to stop if current date < season start
            
            data = scrape_week(year, week)
            all_data.extend(data)
            
            # Be polite to the server
            sleep_time = random.uniform(1.5, 3.0)
            time.sleep(sleep_time)
            
        # Save progress after each year
        print(f"💾 Saving {year} data checkpoint...")
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! Scraped {len(all_data)} total records.")
    print(f"📁 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()