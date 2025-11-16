#!/usr/bin/env python3
"""
Yahoo Defense/Special Teams Scoring System

This module implements Yahoo's default fantasy football scoring for team defenses,
including all defensive stats, special teams returns, and points allowed tiers.
"""

from typing import Dict, Any


class YahooDefenseScoring:
    """
    Yahoo Fantasy Football Defense/Special Teams scoring calculator.

    Implements the standard Yahoo scoring system with:
    - Defensive stats (sacks, interceptions, fumbles, etc.)
    - Special teams return TDs
    - Points allowed tiers
    - Miscellaneous defensive scoring
    """

    # Scoring constants
    SCORING_RULES = {
        # Defensive Touchdowns
        'kickoff_return_td': 6,
        'punt_return_td': 6,
        'interception_return_td': 6,
        'fumble_return_td': 6,
        'blocked_kick_return_td': 6,

        # Defensive Stats
        'sack': 1,
        'blocked_kick': 2,  # Blocked Punt, PAT, or FG
        'interception': 2,
        'fumble_recovery': 2,
        'safety': 2,

        # Points Allowed Tiers
        'points_allowed_0': 10,
        'points_allowed_1_6': 7,
        'points_allowed_7_13': 4,
        'points_allowed_14_17': 1,
        'points_allowed_18_21': 0,
        'points_allowed_22_27': -1,
        'points_allowed_28_34': -4,
        'points_allowed_35_45': -7,
        'points_allowed_46_plus': -10,

        # Miscellaneous (offensive penalties for defense)
        'fumble_lost_by_defense': -2,  # When defense loses fumble on return/recovery
    }

    def __init__(self):
        """Initialize the Yahoo defense scoring calculator."""
        pass

    def calculate_points_allowed_score(self, points_allowed: int) -> int:
        """
        Calculate fantasy points based on points allowed by defense.

        Args:
            points_allowed: Total points allowed by the defense in the game

        Returns:
            Fantasy points earned for points allowed tier
        """
        if points_allowed == 0:
            return self.SCORING_RULES['points_allowed_0']
        elif 1 <= points_allowed <= 6:
            return self.SCORING_RULES['points_allowed_1_6']
        elif 7 <= points_allowed <= 13:
            return self.SCORING_RULES['points_allowed_7_13']
        elif 14 <= points_allowed <= 17:
            return self.SCORING_RULES['points_allowed_14_17']
        elif 18 <= points_allowed <= 21:
            return self.SCORING_RULES['points_allowed_18_21']
        elif 22 <= points_allowed <= 27:
            return self.SCORING_RULES['points_allowed_22_27']
        elif 28 <= points_allowed <= 34:
            return self.SCORING_RULES['points_allowed_28_34']
        elif 35 <= points_allowed <= 45:
            return self.SCORING_RULES['points_allowed_35_45']
        else:  # 46+
            return self.SCORING_RULES['points_allowed_46_plus']

    def calculate_total_fantasy_points(self, stats: Dict[str, Any]) -> float:
        """
        Calculate total fantasy points for a team defense.

        Args:
            stats: Dictionary containing defensive stats for the game

        Expected stats keys:
            - sacks: Number of sacks
            - interceptions: Number of interceptions
            - fumble_recoveries: Number of fumbles recovered
            - safeties: Number of safeties
            - blocked_kicks: Number of blocked punts/FGs/PATs
            - def_touchdowns: Number of defensive TDs
            - kickoff_return_tds: Number of kickoff return TDs
            - punt_return_tds: Number of punt return TDs
            - points_allowed: Points allowed by defense
            - fumbles_lost: Fumbles lost by defense (optional)

        Returns:
            Total fantasy points earned
        """
        total_points = 0.0

        # Basic defensive stats
        total_points += stats.get('sacks', 0) * self.SCORING_RULES['sack']
        total_points += stats.get('interceptions', 0) * self.SCORING_RULES['interception']
        total_points += stats.get('fumble_recoveries', 0) * self.SCORING_RULES['fumble_recovery']
        total_points += stats.get('safeties', 0) * self.SCORING_RULES['safety']
        total_points += stats.get('blocked_kicks', 0) * self.SCORING_RULES['blocked_kick']

        # Defensive/Return touchdowns
        total_points += stats.get('def_touchdowns', 0) * self.SCORING_RULES['interception_return_td']
        total_points += stats.get('kickoff_return_tds', 0) * self.SCORING_RULES['kickoff_return_td']
        total_points += stats.get('punt_return_tds', 0) * self.SCORING_RULES['punt_return_td']
        total_points += stats.get('fumble_return_tds', 0) * self.SCORING_RULES['fumble_return_td']
        total_points += stats.get('blocked_kick_return_tds', 0) * self.SCORING_RULES['blocked_kick_return_td']

        # Points allowed tier
        points_allowed = stats.get('points_allowed', 0)
        total_points += self.calculate_points_allowed_score(points_allowed)

        # Penalties (fumbles lost by defense)
        total_points += stats.get('fumbles_lost', 0) * self.SCORING_RULES['fumble_lost_by_defense']

        return total_points

    def get_scoring_breakdown(self, stats: Dict[str, Any]) -> Dict[str, float]:
        """
        Get detailed breakdown of how fantasy points were earned.

        Args:
            stats: Dictionary containing defensive stats

        Returns:
            Dictionary with breakdown of points by category
        """
        breakdown = {}

        # Basic defensive stats
        breakdown['sacks'] = stats.get('sacks', 0) * self.SCORING_RULES['sack']
        breakdown['interceptions'] = stats.get('interceptions', 0) * self.SCORING_RULES['interception']
        breakdown['fumble_recoveries'] = stats.get('fumble_recoveries', 0) * self.SCORING_RULES['fumble_recovery']
        breakdown['safeties'] = stats.get('safeties', 0) * self.SCORING_RULES['safety']
        breakdown['blocked_kicks'] = stats.get('blocked_kicks', 0) * self.SCORING_RULES['blocked_kick']

        # Touchdowns
        breakdown['def_touchdowns'] = stats.get('def_touchdowns', 0) * self.SCORING_RULES['interception_return_td']
        breakdown['kickoff_return_tds'] = stats.get('kickoff_return_tds', 0) * self.SCORING_RULES['kickoff_return_td']
        breakdown['punt_return_tds'] = stats.get('punt_return_tds', 0) * self.SCORING_RULES['punt_return_td']
        breakdown['fumble_return_tds'] = stats.get('fumble_return_tds', 0) * self.SCORING_RULES['fumble_return_td']
        breakdown['blocked_kick_return_tds'] = stats.get('blocked_kick_return_tds', 0) * self.SCORING_RULES['blocked_kick_return_td']

        # Points allowed
        points_allowed = stats.get('points_allowed', 0)
        breakdown['points_allowed'] = self.calculate_points_allowed_score(points_allowed)

        # Penalties
        breakdown['fumbles_lost'] = stats.get('fumbles_lost', 0) * self.SCORING_RULES['fumble_lost_by_defense']

        # Total
        breakdown['total'] = sum(breakdown.values())

        return breakdown

    def print_scoring_rules(self) -> None:
        """Print all Yahoo defense scoring rules for reference."""
        print("Yahoo Fantasy Football - Defense/Special Teams Scoring")
        print("=" * 60)

        print("\nDefensive Touchdowns:")
        print(f"  Kickoff Return TD: {self.SCORING_RULES['kickoff_return_td']} pts")
        print(f"  Punt Return TD: {self.SCORING_RULES['punt_return_td']} pts")
        print(f"  Interception Return TD: {self.SCORING_RULES['interception_return_td']} pts")
        print(f"  Fumble Return TD: {self.SCORING_RULES['fumble_return_td']} pts")
        print(f"  Blocked Kick Return TD: {self.SCORING_RULES['blocked_kick_return_td']} pts")

        print("\nDefensive Stats:")
        print(f"  Each Sack: {self.SCORING_RULES['sack']} pt")
        print(f"  Blocked Kick: {self.SCORING_RULES['blocked_kick']} pts")
        print(f"  Each Interception: {self.SCORING_RULES['interception']} pts")
        print(f"  Each Fumble Recovery: {self.SCORING_RULES['fumble_recovery']} pts")
        print(f"  Each Safety: {self.SCORING_RULES['safety']} pts")

        print("\nPoints Allowed Tiers:")
        print(f"  0 points allowed: {self.SCORING_RULES['points_allowed_0']} pts")
        print(f"  1-6 points allowed: {self.SCORING_RULES['points_allowed_1_6']} pts")
        print(f"  7-13 points allowed: {self.SCORING_RULES['points_allowed_7_13']} pts")
        print(f"  14-17 points allowed: {self.SCORING_RULES['points_allowed_14_17']} pt")
        print(f"  18-21 points allowed: {self.SCORING_RULES['points_allowed_18_21']} pts")
        print(f"  22-27 points allowed: {self.SCORING_RULES['points_allowed_22_27']} pt")
        print(f"  28-34 points allowed: {self.SCORING_RULES['points_allowed_28_34']} pts")
        print(f"  35-45 points allowed: {self.SCORING_RULES['points_allowed_35_45']} pts")
        print(f"  46+ points allowed: {self.SCORING_RULES['points_allowed_46_plus']} pts")

        print("\nPenalties:")
        print(f"  Fumble Lost by Defense: {self.SCORING_RULES['fumble_lost_by_defense']} pts")


if __name__ == "__main__":
    # Example usage
    scoring = YahooDefenseScoring()

    # Print scoring rules
    scoring.print_scoring_rules()

    # Example game stats
    print("\n" + "=" * 60)
    print("EXAMPLE: Ravens Defense Week 1")
    print("=" * 60)

    ravens_stats = {
        'sacks': 2,
        'interceptions': 1,
        'fumble_recoveries': 0,
        'safeties': 0,
        'blocked_kicks': 0,
        'def_touchdowns': 0,
        'kickoff_return_tds': 0,
        'punt_return_tds': 0,
        'fumble_return_tds': 0,
        'blocked_kick_return_tds': 0,
        'points_allowed': 20,  # Allowed 20 points
        'fumbles_lost': 0
    }

    breakdown = scoring.get_scoring_breakdown(ravens_stats)
    total = scoring.calculate_total_fantasy_points(ravens_stats)

    print("\nScoring Breakdown:")
    for category, points in breakdown.items():
        if points != 0 and category != 'total':
            print(f"  {category}: {points} pts")

    print(f"\nTotal Fantasy Points: {total}")