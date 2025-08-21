#!/usr/bin/env python3
"""
Populate player stubs for Go Fantasy Football Tool
Creates simple stub files for all players so the Go code can run.
"""

import csv
from pathlib import Path


def create_player_stubs():
    """Create stub markdown files for all players from CSV"""
    go_dir = Path(__file__).parent
    analysis_dir = go_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    
    # Find CSV file
    csv_file = go_dir / "combined_with_depth.csv"
    if not csv_file.exists():
        print(f"ERROR: {csv_file} not found")
        return
    
    print(f"Reading players from {csv_file}")
    
    # Read players and create stubs
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        created = 0
        
        for row in reader:
            name = row['Name'].strip()
            clean_name = name.replace('/', '_').replace('\\', '_')
            stub_file = analysis_dir / f"{clean_name}.md"
            
            # Simple stub content
            content = f"# {name}\n\n**Team:** {row['Team']}  \n**Position:** {row['Pos']}  \n\n## Analysis\nPlayer analysis goes here.\n"
            
            stub_file.write_text(content, encoding='utf-8')
            created += 1
    
    print(f"Created {created} player stub files")


def create_status_files():
    """Create status directory and files"""
    go_dir = Path(__file__).parent
    status_dir = go_dir / "status"
    status_dir.mkdir(exist_ok=True)
    
    (status_dir / "pick.txt").write_text("0")
    (status_dir / "current_team.txt").write_text("My Team")
    print("Created status files")


def create_env_file():
    """Create .env file"""
    go_dir = Path(__file__).parent
    env_file = go_dir / ".env"
    
    if not env_file.exists():
        env_file.write_text('OPENAI_API_KEY="your_openai_api_key_here"\n')
        print("Created .env file - add your OpenAI API key!")


def main():
    """Create all necessary files for Go app"""
    print("Creating player stubs...")
    create_player_stubs()
    create_status_files()
    create_env_file()
    print("Done! Run 'go run .' to start the app.")


if __name__ == "__main__":
    main()
