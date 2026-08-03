#!/usr/bin/env python3
"""
RB Opportunity Score Calculator

Usage:
    python get_opportunity_scores.py 2025 5        # Get 2025 Week 5 scores
    python get_opportunity_scores.py 2024 10       # Get 2024 Week 10 scores

This script uses a pre-trained model to calculate opportunity scores for RBs in any given week.
The model was trained on 2022-2024 data and saved as 'rb_opportunity_model_2022_2024.pkl'
"""

import sys
import argparse
from rb_opportunity_model import get_rb_opportunity_scores

def main():
    parser = argparse.ArgumentParser(description='Get RB opportunity scores for any year/week')
    parser.add_argument('year', type=int, help='NFL season year (e.g., 2025)')
    parser.add_argument('week', type=int, help='Week number (1-18)')
    parser.add_argument('--no-csv', action='store_true', help='Skip saving CSV file')
    parser.add_argument('--top-n', type=int, default=20, help='Number of top players to show (default: 20)')

    args = parser.parse_args()

    # Validate inputs
    if args.year < 2020 or args.year > 2030:
        print("Error: Year should be between 2020 and 2030")
        return

    if args.week < 1 or args.week > 22:
        print("Error: Week should be between 1 and 22")
        return

    # Get opportunity scores
    save_csv = not args.no_csv
    result = get_rb_opportunity_scores(args.year, args.week, save_csv=save_csv, show_top_n=args.top_n)

    if result is not None:
        print(f"\n✅ Successfully generated opportunity scores for {args.year} Week {args.week}")
        if save_csv:
            print(f"📁 Results saved to: rb_opportunity_scores_{args.year}_week{args.week}.csv")
    else:
        print(f"\n❌ Failed to generate opportunity scores for {args.year} Week {args.week}")

if __name__ == "__main__":
    main()