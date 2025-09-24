# Ramalama Setup for Player Notes

## Installation

1. Install ramalama:
   ```bash
   pip install -r requirements.txt
   ```

## Model Setup

The system will automatically detect your hardware and install an appropriate model:

- **16GB+ RAM**: `llama3:8b` (better quality)
- **<16GB RAM**: `phi3:mini` (lighter weight)

## Usage

The GUI will have two buttons:
- **Scrape Note Data**: Collects player notes from external sources
- **Regenerate Notes**: Uses ramalama to summarize player notes and caches them locally

## Manual Commands

If you want to use ramalama directly:

```bash
# Pull a model
ramalama pull llama3:8b

# Run inference
ramalama run llama3:8b "Summarize this player: [player info]"
```

## File Structure

- `player-notes/`: Directory containing cached player summaries
- `start-sit-weekly/player_notes.py`: Automation script for note processing