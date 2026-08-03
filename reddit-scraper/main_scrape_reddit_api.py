#!/usr/bin/env python3
"""
Robust Reddit API scraper for fantasy football player analysis with tiered matching.

This version improves accuracy by:
1. Implementing tiered matching (high-confidence vs medium-confidence)
2. Robust name normalization handling punctuation (A.J. -> AJ)
3. Separating results by confidence level for GPT processing
4. Better handling of common names and nicknames
5. Accuracy scoring for each match
"""

from RedditQuery import RedditQuery
from FootballPlayer import FootballPlayer

import re
import os
import pathlib
import time
import praw
from typing import Set, Tuple, Optional, List, Dict, NamedTuple
import json
from dataclasses import dataclass
from enum import Enum

from pipeline_utils import current_season_year

# Configuration
SUFFIXES = ["Jr.", "Sr.", "II", "III", "IV", "V"]
SUBREDDIT = "fantasyfootball"
POST_LIMIT = 50
DAYS_BACK = 60
CONTEXT_LINES = 3  # Lines before and after relevant content (like grep -C 3)

# Directories
FILTERED_DIR = "filtered_data"

class MatchConfidence(Enum):
    HIGH = "high_confidence"      # Full name or nickname matches
    MEDIUM = "medium_confidence"  # Last name only matches
    LOW = "low_confidence"        # Very common names, likely false positives

@dataclass
class PlayerMatch:
    """Represents a matched player mention with confidence scoring."""
    original_text: str
    normalized_text: str
    match_type: str  # "full_name", "nickname", "last_name"
    confidence: MatchConfidence
    search_term_used: str


def normalize_name_for_matching(name: str) -> str:
    """
    Normalize name for robust matching by removing punctuation and standardizing.
    
    Examples:
    - "A.J. Brown" -> "aj brown"
    - "D.K. Metcalf" -> "dk metcalf"
    - "Amon-Ra St. Brown" -> "amonra st brown"
    """
    if not name:
        return ""
    
    # Remove suffixes first
    suffix_pattern = r"\s+(?:" + "|".join(map(re.escape, SUFFIXES)) + r")$"
    name = re.sub(suffix_pattern, "", name).strip()
    
    # Convert to lowercase
    name = name.lower()
    
    # Remove periods and hyphens from initials/names
    # A.J. -> aj, D.K. -> dk, Amon-Ra -> amonra
    name = re.sub(r'\.', '', name)
    name = re.sub(r'-', '', name)
    
    # Clean up extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def create_name_variations(full_name: str, nickname: str = "") -> Dict[str, str]:
    """
    Create all possible name variations for a player.
    
    Returns dict mapping variation type to normalized name.
    """
    variations = {}
    
    # Normalize the full name
    normalized_full = normalize_name_for_matching(full_name)
    if normalized_full:
        variations['full_name'] = normalized_full
    
    # Handle nickname
    if nickname and str(nickname).strip():
        normalized_nickname = normalize_name_for_matching(str(nickname).strip())
        if normalized_nickname and normalized_nickname != normalized_full:
            variations['nickname'] = normalized_nickname
    
    # Extract parts for additional variations
    name_parts = normalized_full.split() if normalized_full else []
    
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # Add last name only (for medium confidence matching)
        variations['last_name'] = last_name
        
        # Add first name only (for very low confidence, probably skip this)
        # variations['first_name'] = first_name
        
        # Handle middle names/initials - create variations
        if len(name_parts) > 2:
            middle_parts = name_parts[1:-1]
            
            # "First Middle Last" format
            variations['full_name_expanded'] = normalized_full
            
            # "First M Last" format (first letter of middle name)
            if middle_parts:
                middle_initial = middle_parts[0][0] if middle_parts[0] else ""
                if middle_initial:
                    first_middle_last = f"{first_name} {middle_initial} {last_name}"
                    variations['first_middle_last'] = first_middle_last
    
    return variations


def get_duplicate_last_names_from_dataset(players: List[FootballPlayer]) -> Set[str]:
    """
    Dynamically detect last names that appear for multiple players in the dataset.
    These should get lower confidence when matching by last name only.
    """
    last_name_counts = {}
    
    for player in players:
        # Get the normalized last name
        normalized_full = normalize_name_for_matching(player.player_name)
        name_parts = normalized_full.split()
        
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            last_name_counts[last_name] = last_name_counts.get(last_name, 0) + 1
    
    # Return last names that appear for 2+ players
    duplicate_names = {name for name, count in last_name_counts.items() if count > 1}
    
    return duplicate_names


def determine_match_confidence(
    match_type: str, 
    last_name: str, 
    duplicate_last_names: Set[str]
) -> MatchConfidence:
    """
    Determine confidence level for a match based on type and dataset analysis.
    
    Args:
        match_type: Type of match (full_name, nickname, last_name, etc.)
        last_name: The last name being matched
        duplicate_last_names: Set of last names that appear multiple times in dataset
    """
    # High confidence: full name or nickname matches
    if match_type in ['full_name', 'nickname', 'full_name_expanded', 'first_middle_last']:
        return MatchConfidence.HIGH
    
    # Medium to low confidence: last name only
    if match_type in ['last_name']:
        # If multiple players share this last name, lower confidence
        if last_name.lower() in duplicate_last_names:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.MEDIUM
    
    # Default to medium confidence
    return MatchConfidence.MEDIUM


def sanitize_name_for_search(name: str) -> str:
    """Legacy function - kept for backwards compatibility."""
    return normalize_name_for_matching(name)


def generate_player_search_terms(player: FootballPlayer) -> Dict[str, str]:
    """
    Generate comprehensive search terms for a player with confidence levels.
    
    Returns:
        Dict mapping search term type to the actual search term
    """
    # Get all name variations using the robust system
    variations = create_name_variations(
        player.player_name, 
        getattr(player, 'player_nickname', '')
    )
    
    return variations


def create_player_regex_patterns(search_terms: Dict[str, str], duplicate_last_names: Set[str]) -> Dict[str, List[re.Pattern]]:
    """
    Create regex patterns for robust player name matching.
    
    Returns patterns organized by match type for confidence assessment.
    """
    pattern_groups = {
        'high_confidence': [],
        'medium_confidence': [],
        'low_confidence': []
    }
    
    for match_type, term in search_terms.items():
        if not term:
            continue
            
        # Create multiple pattern variations for each term to handle different formats
        patterns_for_term = []
        
        # Basic pattern with word boundaries
        escaped_term = re.escape(term)
        basic_pattern = re.compile(rf'\b{escaped_term}\b', re.IGNORECASE)
        patterns_for_term.append(basic_pattern)
        
        # For names with spaces, also try without spaces (handles "AJ Brown" vs "A.J. Brown")
        if ' ' in term:
            no_space_term = term.replace(' ', '')
            if len(no_space_term) > 2:  # Avoid matching very short terms
                no_space_pattern = re.compile(rf'\b{re.escape(no_space_term)}\b', re.IGNORECASE)
                patterns_for_term.append(no_space_pattern)
        
        # For names with initials, create variations
        # "aj brown" should also match "a.j. brown", "a j brown", "AJ brown"
        if len(term.split()) > 1:
            first_part = term.split()[0]
            rest_parts = ' '.join(term.split()[1:])
            
            # If first part looks like initials (2 chars or less), create variations
            if len(first_part) <= 2:
                # "aj" -> matches "a.j.", "a j", "a. j.", etc.
                if len(first_part) == 2:
                    char1, char2 = first_part[0], first_part[1]
                    variations = [
                        f"{char1}\\.{char2}\\. {re.escape(rest_parts)}",
                        f"{char1}\\. {char2}\\. {re.escape(rest_parts)}",
                        f"{char1} {char2} {re.escape(rest_parts)}",
                        f"{char1}{char2} {re.escape(rest_parts)}",  # already covered by basic
                    ]
                    for var in variations:
                        var_pattern = re.compile(rf'\b{var}\b', re.IGNORECASE)
                        patterns_for_term.append(var_pattern)
        
        # Categorize patterns by confidence level
        if match_type in ['full_name', 'nickname', 'full_name_expanded', 'first_middle_last']:
            pattern_groups['high_confidence'].extend(patterns_for_term)
        elif match_type in ['last_name']:
            # Check if multiple players in dataset have this last name
            last_name = term.lower()
            if last_name in duplicate_last_names:
                pattern_groups['low_confidence'].extend(patterns_for_term)
            else:
                pattern_groups['medium_confidence'].extend(patterns_for_term)
        else:
            pattern_groups['medium_confidence'].extend(patterns_for_term)
    
    return pattern_groups


def extract_relevant_content_exact_lines(
    text: str, 
    pattern_groups: Dict[str, List[re.Pattern]]
) -> Dict[str, List[Tuple[str, MatchConfidence]]]:
    """
    Extract only the exact lines containing player mentions (no context).
    
    Returns:
        Dict mapping confidence level to list of (content, confidence) tuples
    """
    if not text or not pattern_groups:
        return {
            'high_confidence': [],
            'medium_confidence': [],
            'low_confidence': []
        }
    
    lines = text.split('\n')
    matched_sections_by_confidence = {
        'high_confidence': [],
        'medium_confidence': [],
        'low_confidence': []
    }
    
    # Process each confidence level separately
    for confidence_level, patterns in pattern_groups.items():
        if not patterns:
            continue
            
        matched_lines = []
        
        # Find all lines that match any pattern at this confidence level
        for line in lines:
            for pattern in patterns:
                if pattern.search(line):
                    if line.strip():  # Only add non-empty lines
                        matched_lines.append(line)
                    break
        
        if not matched_lines:
            continue
        
        # Create confidence enum
        confidence_enum = MatchConfidence.HIGH if confidence_level == 'high_confidence' else \
                         MatchConfidence.MEDIUM if confidence_level == 'medium_confidence' else \
                         MatchConfidence.LOW
        
        # Join all matched lines for this confidence level
        section_text = '\n'.join(matched_lines)
        if section_text.strip():
            matched_sections_by_confidence[confidence_level].append(
                (section_text, confidence_enum)
            )
    
    return matched_sections_by_confidence


def extract_relevant_content_with_context(
    text: str, 
    pattern_groups: Dict[str, List[re.Pattern]], 
    context_lines: int = CONTEXT_LINES
) -> Dict[str, List[Tuple[str, MatchConfidence]]]:
    """
    Extract lines containing player mentions with surrounding context and confidence levels.
    
    Returns:
        Dict mapping confidence level to list of (content, confidence) tuples
    """
    if not text or not pattern_groups:
        return {
            'high_confidence': [],
            'medium_confidence': [],
            'low_confidence': []
        }
    
    lines = text.split('\n')
    matched_sections_by_confidence = {
        'high_confidence': [],
        'medium_confidence': [],
        'low_confidence': []
    }
    
    # Process each confidence level separately
    for confidence_level, patterns in pattern_groups.items():
        if not patterns:
            continue
            
        matched_line_indices = set()
        
        # Find all lines that match any pattern at this confidence level
        for i, line in enumerate(lines):
            for pattern in patterns:
                if pattern.search(line):
                    matched_line_indices.add(i)
                    break
        
        if not matched_line_indices:
            continue
        
        # Extract context around matched lines
        context_ranges = []
        for line_idx in matched_line_indices:
            start = max(0, line_idx - context_lines)
            end = min(len(lines), line_idx + context_lines + 1)
            context_ranges.append((start, end))
        
        # Merge overlapping ranges
        context_ranges.sort()
        merged_ranges = []
        for start, end in context_ranges:
            if merged_ranges and start <= merged_ranges[-1][1]:
                # Overlapping or adjacent ranges - merge them
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], end))
            else:
                merged_ranges.append((start, end))
        
        # Extract the actual content for this confidence level
        confidence_enum = MatchConfidence.HIGH if confidence_level == 'high_confidence' else \
                         MatchConfidence.MEDIUM if confidence_level == 'medium_confidence' else \
                         MatchConfidence.LOW
        
        for start, end in merged_ranges:
            section_lines = lines[start:end]
            section_text = '\n'.join(section_lines)
            if section_text.strip():
                matched_sections_by_confidence[confidence_level].append(
                    (section_text, confidence_enum)
                )
    
    return matched_sections_by_confidence


def filter_reddit_content(content: str, pattern_groups: Dict[str, List[re.Pattern]], use_exact_lines: bool = True) -> Dict[str, any]:
    """
    Filter Reddit content to extract only relevant portions with confidence levels.
    Returns both the filtered content and metadata about the filtering.
    """
    if not content or not pattern_groups:
        return {
            'filtered_content_by_confidence': {
                'high_confidence': '',
                'medium_confidence': '',
                'low_confidence': ''
            },
            'original_length': len(content) if content else 0,
            'filtered_length': 0,
            'sections_found_by_confidence': {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0
            },
            'compression_ratio': 0.0
        }
    
    original_length = len(content)
    
    # Use exact line matching instead of context-based matching
    if use_exact_lines:
        relevant_sections_by_confidence = extract_relevant_content_exact_lines(content, pattern_groups)
    else:
        relevant_sections_by_confidence = extract_relevant_content_with_context(content, pattern_groups)
    
    filtered_content_by_confidence = {}
    total_sections_found = 0
    total_filtered_length = 0
    
    for confidence_level, sections in relevant_sections_by_confidence.items():
        if sections:
            # Extract just the content (not the confidence enum)
            section_texts = [section_text for section_text, _ in sections]
            
            # Join sections with clear separators
            filtered_content = f'\n\n--- {confidence_level.upper().replace("_", " ")} SECTION ---\n\n'.join(section_texts)
            filtered_content_by_confidence[confidence_level] = filtered_content
            total_filtered_length += len(filtered_content)
            total_sections_found += len(sections)
        else:
            filtered_content_by_confidence[confidence_level] = ''
    
    compression_ratio = (original_length - total_filtered_length) / original_length if original_length > 0 else 0.0
    
    return {
        'filtered_content_by_confidence': filtered_content_by_confidence,
        'original_length': original_length,
        'filtered_length': total_filtered_length,
        'sections_found_by_confidence': {
            conf: len(sections) for conf, sections in relevant_sections_by_confidence.items()
        },
        'compression_ratio': compression_ratio
    }


def get_reddit_submissions_efficiently(reddit_client: RedditQuery, search_terms: Dict[str, str]) -> List[praw.models.Submission]:
    """Get Reddit submissions with more targeted searches."""
    all_submissions = []
    seen_submission_ids = set()
    
    # Convert search terms dict to list of unique terms
    unique_terms = set()
    for term_type, term in search_terms.items():
        if term and len(term.strip()) > 1:  # Skip very short terms
            unique_terms.add(term.strip())
    
    # Use more specific search queries
    for term in unique_terms:
        print(f"Searching for posts with term: '{term}'...")
        
        # Try different search strategies
        season = current_season_year()
        search_queries = [
            f'"{term}"',  # Exact match
            f'{term} AND (fantasy OR draft OR waiver)',  # Fantasy context
            f'{term} AND ({season} OR {season - 1})',  # Recent years
        ]
        
        for query in search_queries:
            try:
                submissions = reddit_client.search_subreddit(
                    SUBREDDIT, query, limit=POST_LIMIT//len(search_queries)
                )
                
                for sub in submissions:
                    if sub.id not in seen_submission_ids:
                        all_submissions.append(sub)
                        seen_submission_ids.add(sub.id)
                        
            except Exception as e:
                print(f"Search failed for query '{query}': {e}")
                continue
    
    return all_submissions


def process_reddit_post_efficiently(
    reddit_client: RedditQuery, 
    post: praw.models.Submission, 
    pattern_groups: Dict[str, List[re.Pattern]],
    player_name: str
) -> Dict[str, any]:
    """Process a single Reddit post with confidence-based filtering."""
    
    result = {
        'post_title': post.title,
        'post_url': post.url,
        'post_id': post.id,
        'relevant_content_by_confidence': {
            'high_confidence': [],
            'medium_confidence': [],
            'low_confidence': []
        },
        'total_comments_processed': 0,
        'relevant_sections_found_by_confidence': {
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0
        },
        'compression_stats': {
            'original_size': 0,
            'filtered_size': 0,
            'compression_ratio': 0.0
        }
    }
    
    # Process post content
    post_content = reddit_client.fetch_post_content(post)
    post_filter_result = filter_reddit_content(post_content, pattern_groups, use_exact_lines=True)
    
    # Add post content if relevant
    for confidence_level, content in post_filter_result['filtered_content_by_confidence'].items():
        if content:
            result['relevant_content_by_confidence'][confidence_level].append({
                'type': 'post',
                'content': content,
                'metadata': post_filter_result
            })
            result['relevant_sections_found_by_confidence'][confidence_level] += \
                post_filter_result['sections_found_by_confidence'][confidence_level]
    
    # Process comments with early filtering
    try:
        comment_chains = reddit_client.fetch_comments_chains(post)
        result['total_comments_processed'] = sum(len(chain) for chain in comment_chains)
        
        for chain_idx, chain in enumerate(comment_chains):
            # First check if any comment in the chain mentions the player
            chain_text = '\n'.join(chain)
            
            # Quick check before expensive filtering - check all patterns
            has_player_mention = False
            for patterns in pattern_groups.values():
                if any(pattern.search(chain_text) for pattern in patterns):
                    has_player_mention = True
                    break
            
            if has_player_mention:
                chain_filter_result = filter_reddit_content(chain_text, pattern_groups, use_exact_lines=True)
                
                # Add chain content by confidence level
                for confidence_level, content in chain_filter_result['filtered_content_by_confidence'].items():
                    if content:
                        result['relevant_content_by_confidence'][confidence_level].append({
                            'type': 'comment_chain',
                            'chain_index': chain_idx,
                            'content': content,
                            'metadata': chain_filter_result
                        })
                        result['relevant_sections_found_by_confidence'][confidence_level] += \
                            chain_filter_result['sections_found_by_confidence'][confidence_level]
        
    except Exception as e:
        print(f"Error processing comments for post {post.id}: {e}")
    
    # Calculate overall compression stats
    total_original = 0
    total_filtered = 0
    
    for confidence_content_list in result['relevant_content_by_confidence'].values():
        for item in confidence_content_list:
            total_original += item['metadata']['original_length']
            total_filtered += item['metadata']['filtered_length']
    
    result['compression_stats'] = {
        'original_size': total_original,
        'filtered_size': total_filtered,
        'compression_ratio': (total_original - total_filtered) / total_original if total_original > 0 else 0.0
    }
    
    return result


def save_reddit_processing_results(
    player: FootballPlayer,
    posts_results: List[Dict],
    filtered_dir: str
) -> Dict[str, any]:
    """Save filtered results with confidence-based separation."""

    os.makedirs(filtered_dir, exist_ok=True)
    
    # Aggregate content by confidence level
    content_by_confidence = {
        'high_confidence': [],
        'medium_confidence': [],
        'low_confidence': []
    }
    
    processing_stats = {
        'total_posts_processed': len(posts_results),
        'posts_with_relevant_content': 0,
        'sections_found_by_confidence': {
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0
        },
        'total_original_size': 0,
        'total_filtered_size': 0,
        'overall_compression_ratio': 0.0
    }
    
    for post_result in posts_results:
        # Check if this post has any relevant content at any confidence level
        has_content = any(
            post_result['relevant_content_by_confidence'][conf] 
            for conf in ['high_confidence', 'medium_confidence', 'low_confidence']
        )
        
        if has_content:
            processing_stats['posts_with_relevant_content'] += 1
            processing_stats['total_original_size'] += post_result['compression_stats']['original_size']
            processing_stats['total_filtered_size'] += post_result['compression_stats']['filtered_size']
            
            # Process content for each confidence level
            for confidence_level in ['high_confidence', 'medium_confidence', 'low_confidence']:
                content_items = post_result['relevant_content_by_confidence'][confidence_level]
                
                if content_items:
                    processing_stats['sections_found_by_confidence'][confidence_level] += \
                        post_result['relevant_sections_found_by_confidence'][confidence_level]
                    
                    # Format content for saving
                    post_content_parts = []
                    post_content_parts.append(f"=== POST: {post_result['post_title']} ===")
                    post_content_parts.append(f"URL: {post_result['post_url']}")
                    post_content_parts.append("")
                    
                    for content_item in content_items:
                        if content_item['type'] == 'post':
                            post_content_parts.append("--- POST CONTENT ---")
                        else:
                            post_content_parts.append(f"--- COMMENT CHAIN {content_item['chain_index']} ---")
                        
                        post_content_parts.append(content_item['content'])
                        post_content_parts.append("")
                    
                    content_by_confidence[confidence_level].append('\n'.join(post_content_parts))
    
    # Calculate overall compression ratio
    if processing_stats['total_original_size'] > 0:
        processing_stats['overall_compression_ratio'] = (
            processing_stats['total_original_size'] - processing_stats['total_filtered_size']
        ) / processing_stats['total_original_size']
    
    # Save filtered Reddit content only (no FF Hound processing)
    filtered_file = os.path.join(filtered_dir, f"{player.slug}_reddit_discussion.txt")
    
    with open(filtered_file, "w", encoding="utf-8") as f:
        f.write(f"REDDIT FANTASY FOOTBALL ANALYSIS FOR {player.player_name.upper()}\n")
        f.write("=" * 80 + "\n\n")

        post_separator = '\n\n' + '=' * 80 + '\n\n'
        high_confidence = post_separator.join(content_by_confidence['high_confidence'])

        if high_confidence:
            f.write("--- HIGH CONFIDENCE REDDIT DISCUSSION ---\n\n")
            f.write(high_confidence)
            f.write("\n\n")
        else:
            f.write(f"No relevant Reddit discussion found for {player.player_name}")
    
    # Save processing metadata
    metadata_file = os.path.join(filtered_dir, f"{player.slug}_processing_metadata.json")
    metadata = {
        'player_name': player.player_name,
        'player_slug': player.slug,
        'processing_stats': processing_stats,
        'posts_processed': [
            {
                'post_id': result['post_id'],
                'post_title': result['post_title'],
                'sections_by_confidence': result['relevant_sections_found_by_confidence'],
                'compression_ratio': result['compression_stats']['compression_ratio']
            }
            for result in posts_results if any(
                result['relevant_content_by_confidence'][conf] 
                for conf in ['high_confidence', 'medium_confidence', 'low_confidence']
            )
        ]
    }
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    return processing_stats


def get_processed_players(filtered_dir: str) -> Set[str]:
    """Get set of players that have already been processed."""
    processed = set()
    if not os.path.isdir(filtered_dir):
        return processed

    for filename in os.listdir(filtered_dir):
        if filename.endswith("_reddit_discussion.txt"):
            slug = filename[:-len("_reddit_discussion.txt")]
            processed.add(slug)

    return processed


def main():
    """Main execution function with dynamic duplicate detection."""
    # Setup directories
    script_dir = pathlib.Path(__file__).resolve().parent
    filtered_dir_abs = str((script_dir / FILTERED_DIR).resolve())
    os.makedirs(filtered_dir_abs, exist_ok=True)

    # Initialize clients and load player data
    reddit_client = RedditQuery()
    players: List[FootballPlayer] = FootballPlayer.from_csv("combined_with_depth.csv")
    
    # Dynamically detect duplicate last names in the dataset
    duplicate_last_names = get_duplicate_last_names_from_dataset(players)
    print(f"Detected {len(duplicate_last_names)} duplicate last names in dataset: {sorted(list(duplicate_last_names))}")
    
    # Resume from where we left off
    processed_players = get_processed_players(filtered_dir_abs)
    remaining_players = [p for p in players if p.slug not in processed_players]
    
    print(f"Total players: {len(players)}")
    print(f"Already processed: {len(processed_players)}")
    print(f"Remaining to process: {len(remaining_players)}")
    
    if not remaining_players:
        print("All players have been processed!")
        return
    
    # Process each player with improved efficiency and confidence-based matching
    for i, player in enumerate(remaining_players):
        print(f"\n=== Processing {player.player_name} ({i+1}/{len(remaining_players)}) ===")

        # Generate search terms and regex patterns with robust matching
        search_terms = generate_player_search_terms(player)
        pattern_groups = create_player_regex_patterns(search_terms, duplicate_last_names)
        
        print(f"Search terms: {search_terms}")
        print(f"Pattern groups: {[f'{k}: {len(v)} patterns' for k, v in pattern_groups.items()]}")
        
        # Get Reddit submissions with targeted search
        submissions = get_reddit_submissions_efficiently(reddit_client, search_terms)
        recent_posts = reddit_client.filter_posts_by_date(submissions, days_back=DAYS_BACK)
        
        print(f"Found {len(recent_posts)} recent posts")
        
        if not recent_posts:
            print(f"No recent posts found for {player.player_name}")
            # Marker file so resume logic and the combine step still see this player
            empty_file = os.path.join(filtered_dir_abs, f"{player.slug}_reddit_discussion.txt")
            with open(empty_file, "w", encoding="utf-8") as f:
                f.write(f"REDDIT FANTASY FOOTBALL ANALYSIS FOR {player.player_name.upper()}\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"No relevant Reddit discussion found for {player.player_name}")
            continue
        
        # Process Reddit posts with confidence-based filtering
        posts_results = []
        total_compression_saved = 0
        
        for post in recent_posts:
            post_result = process_reddit_post_efficiently(reddit_client, post, pattern_groups, player.player_name)
            posts_results.append(post_result)
            
            # Track compression savings
            compression_stats = post_result['compression_stats']
            if compression_stats['original_size'] > 0:
                saved_bytes = compression_stats['original_size'] - compression_stats['filtered_size']
                total_compression_saved += saved_bytes
            
            # Rate limiting
            time.sleep(0.3)
        
        # Save results with confidence-based separation
        processing_stats = save_reddit_processing_results(player, posts_results, filtered_dir_abs)
        
        # Report efficiency gains with confidence breakdown
        if processing_stats['total_original_size'] > 0:
            compression_pct = processing_stats['overall_compression_ratio'] * 100
            print(f"Content compressed by {compression_pct:.1f}% "
                  f"({processing_stats['total_original_size']} -> {processing_stats['total_filtered_size']} chars)")
            
            # Report sections by confidence level
            high_conf = processing_stats['sections_found_by_confidence']['high_confidence']
            med_conf = processing_stats['sections_found_by_confidence']['medium_confidence']
            low_conf = processing_stats['sections_found_by_confidence']['low_confidence']
            
            print(f"Sections found - High confidence: {high_conf}, Medium: {med_conf}, Low: {low_conf}")
            print(f"Total across {processing_stats['posts_with_relevant_content']} posts")
        
        # Check API limits
        try:
            limits = reddit_client.reddit.auth.limits
            print(f"Reddit API requests remaining: {limits['remaining']}")
        except:
            pass
        
        print(f"Processed {player.player_name} successfully")


if __name__ == "__main__":
    main()
