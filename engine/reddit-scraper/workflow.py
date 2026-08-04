#!/usr/bin/env python3
"""
Streamlined workflow script for fantasy football batch processing.
This provides a simple menu-driven interface for all batch operations.
"""

import os
import sys
import json
import subprocess
from datetime import datetime


def run_command(command, description):
    """Run a command and show the results."""
    print(f"\n🔄 {description}...")
    print(f"   Running: {command}")
    print("-" * 50)
    
    result = subprocess.run(command, shell=True, capture_output=False)
    
    if result.returncode == 0:
        print(f"✅ {description} completed successfully!")
    else:
        print(f"❌ {description} failed with exit code {result.returncode}")
    
    return result.returncode == 0


def check_batch_status():
    """Check and display current batch status."""
    BATCH_ID_FILE = "batch_info.json"
    
    print("\n📊 CURRENT BATCH STATUS")
    print("=" * 40)
    
    if os.path.exists(BATCH_ID_FILE):
        with open(BATCH_ID_FILE, "r") as f:
            batch_info = json.load(f)
        
        print(f"📄 Batch ID: {batch_info['batch_id']}")
        print(f"📝 Players: {batch_info['player_count']}")
        print(f"📅 Submitted: {batch_info['submitted_at']}")
        print(f"🔄 Status: {batch_info['status']}")
        
        return batch_info['status']
    else:
        print("📭 No active batch found")
        return None


def show_menu():
    """Display the main menu."""
    print("\n🚀 FANTASY FOOTBALL PROCESSOR")
    print("=" * 40)
    print("1. 📊 Check batch status")
    print("2. 🚀 Submit new batch")
    print("3. 📥 Get batch results")
    print("4. 🧹 Reset (delete batch info)")
    print("5. ❌ Cancel current batch")
    print("6. ⚡ Live processing (200 players, GPT-5-nano)")
    print("7. 📖 Show README")
    print("0. 🚪 Exit")
    print("-" * 40)


def main():
    """Main workflow loop."""
    print("Welcome to the Fantasy Football Batch Processor!")
    
    # Check if we're in the right directory
    if not os.path.exists("submit_batch.py"):
        print("❌ Error: Not in the reddit-scraper directory!")
        print("   Please run this from: /path/to/Fantasy-Football-Tool/reddit-scraper/")
        sys.exit(1)
    
    # Check virtual environment
    if not os.environ.get('VIRTUAL_ENV'):
        print("⚠️  Warning: Virtual environment not activated")
        print("   Run: source venv/bin/activate")
        print("   Then try again")
        sys.exit(1)
    
    while True:
        show_menu()
        
        try:
            choice = input("Enter your choice (0-7): ").strip()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)
        
        if choice == "0":
            print("👋 Goodbye!")
            break
            
        elif choice == "1":
            status = check_batch_status()
            if status == "submitted":
                print("\n💡 Tip: Use option 3 to check if results are ready")
            elif status == "completed":
                print("\n💡 Tip: Use option 3 to download results")
            elif status == "downloaded":
                print("\n✅ Results are in the markdown_data/ directory")
            
        elif choice == "2":
            status = check_batch_status()
            if status:
                print(f"\n⚠️  Batch already exists with status: {status}")
                print("   Use option 4 to reset, or option 3 to get results")
            else:
                print("\n🔍 Submitting batch to OpenAI...")
                success = run_command("python submit_batch.py", "Batch submission")
                if success:
                    print("\n✅ Batch submitted successfully!")
                    print("   Processing will take 6-24 hours")
                    print("   Use option 1 to check status anytime")
            
        elif choice == "3":
            status = check_batch_status()
            if not status:
                print("\n❌ No batch found. Submit a batch first (option 2)")
            else:
                success = run_command("python get_batch_results.py", "Getting batch results")
                if success:
                    print("\n📁 Check the markdown_data/ directory for player analyses")
            
        elif choice == "4":
            if os.path.exists("batch_info.json"):
                os.remove("batch_info.json")
                print("\n🧹 Batch info cleared. Ready to submit new batch.")
            else:
                print("\n📭 No batch info to clear.")
            
        elif choice == "5":
            status = check_batch_status()
            if status in ["submitted", "validating", "in_progress", "finalizing"]:
                success = run_command("python cancel_batch_job.py", "Cancelling batch")
                if success:
                    print("\n🚫 Batch cancelled.")
            else:
                print(f"\n⚠️  Cannot cancel batch with status: {status}")
            
        elif choice == "6":
            print("\n⚡ Starting live processing (first 200 non-K/DST players)...")
            success = run_command("python live_process.py", "Live processing with GPT-5-nano")
            if success:
                print("\n✅ Live processing completed!")
                print("   Check the markdown_data/ directory for results")
            
        elif choice == "7":
            print("\n📖 Opening README...")
            if os.path.exists("README.md"):
                run_command("cat README.md | head -50", "Showing README preview")
                print("\n💡 Full README available at: reddit-scraper/README.md")
            else:
                print("❌ README.md not found")
        
        else:
            print("❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
