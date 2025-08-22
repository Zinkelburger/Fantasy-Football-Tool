#!/usr/bin/env python3
"""
Master script to run the full three-step analysis workflow:
1. Reddit scraping (outputs to _reddit files)
2. FF Hound processing (outputs to _ff_hound files) 
3. Combination (outputs to _final_discussion files)

Usage:
    python run_full_analysis.py [--skip-reddit] [--skip-ff-hound] [--skip-combine]
"""

import argparse
import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print(f"✗ Command not found: {command[0]}")
        return False

def main():
    """Run the full analysis workflow"""
    parser = argparse.ArgumentParser(description="Run full fantasy football analysis workflow")
    parser.add_argument("--skip-reddit", action="store_true", help="Skip Reddit scraping step")
    parser.add_argument("--skip-ff-hound", action="store_true", help="Skip FF Hound processing step")
    parser.add_argument("--skip-combine", action="store_true", help="Skip combination step")
    
    args = parser.parse_args()
    
    print("Fantasy Football Analysis Workflow")
    print("=" * 60)
    
    success_count = 0
    total_steps = 0
    
    # Step 1: Reddit Scraping
    if not args.skip_reddit:
        total_steps += 1
        if run_command([sys.executable, "main_scrape_reddit_api.py"], "Reddit Scraping"):
            success_count += 1
        else:
            print("Reddit scraping failed. Stopping workflow.")
            return False
    else:
        print("Skipping Reddit scraping (--skip-reddit)")
    
    # Step 2: FF Hound Processing
    if not args.skip_ff_hound:
        total_steps += 1
        if run_command([sys.executable, "process_ff_hound.py"], "FF Hound Processing"):
            success_count += 1
        else:
            print("FF Hound processing failed. Continuing to combination step...")
    else:
        print("Skipping FF Hound processing (--skip-ff-hound)")
    
    # Step 3: Combination
    if not args.skip_combine:
        total_steps += 1
        if run_command([sys.executable, "combine_analyses.py"], "Analysis Combination"):
            success_count += 1
        else:
            print("Analysis combination failed.")
            return False
    else:
        print("Skipping analysis combination (--skip-combine)")
    
    # Summary
    print(f"\n{'='*60}")
    print("WORKFLOW SUMMARY")
    print(f"{'='*60}")
    print(f"Steps completed successfully: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("✓ All steps completed successfully!")
        print("\nOutput files:")
        print("- *_reddit_discussion.txt: Reddit analysis only")
        print("- *_ff_hound_discussion.txt: FF Hound analysis only") 
        print("- *_final_discussion.txt: Combined analysis")
        return True
    else:
        print("✗ Some steps failed. Check output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
