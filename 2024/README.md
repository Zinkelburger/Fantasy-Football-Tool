# Fantasy Football Tool
Helps suggest relevant players to you during your draft.

A browser extension tracks the players that have been picked so far. It sends this information to a Python script, which filters the remaining player options. This lets ChatGPT give its opinion on the current state of the draft.

# Usage:
## Pre-draft setup:
### Get the data
I used two files:
1. `ADR.csv` = Abusing Draft Rankings, from [JuiceBoxOne Reddit](https://www.reddit.com/r/fantasyfootball/comments/1ezct9b/abusing_draft_rankings_2024_espn_sleeper_yahoo/)
2. `ECR.csv` = Expert Consensus Rankings, downloaded from [FantasyPros](https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php)

Run `parse.py` to generate `combined_with_depth.csv`

### Get the analysis
Put your analysis files in the `analysis` directory
Run `not_found.py` to generate a list of all the players not in the analysis directory, `not_found.csv`
I got the analysis mostly from reddit comments.

### Setup your ChatGPT API Token
You need to get an [OpenAI API Token](https://platform.openai.com/settings/organization/billing/overview)
Put it in `.env`, e.g. `OPENAI_API_KEY=your_api_key`

### Setup your browser
On Firefox, go to <about:debugging>, click "This Firefox", and "Load Temporary Add-on"
Then select the `extension/manifest.json` file
**Make sure its running/reload it if necessary**. Can check its log with "inspect"

## During Draft
1. Run `python3 main_http.py &`
This receives responses from the browser extension, and records the current picked players & pick number in `log/pick.txt` and `log/player_$timestamp`

2. Run `python3 filter.py && python3 ask_gpt.py`
This prints ChatGPT's response to your console. `filter.py` removes picked & irrelevant players so the correct files can be fed to ChatGPT.

3. Update `log/current_team.txt` during your draft

Note you can change the model, I currently have it as `GPT_MODEL = "gpt-4o"`

# Notes/TODO
I couldn't figure out how to get `Depth.csv` from [FantastyPros](https://www.fantasypros.com/nfl/depth-charts.php), so I just rank the players WR1, etc. based on their ADP rankings.

I try to log all relevant the files with a timestamp in case something crashes.

I can see it being very hard to use this if you aren't familiar with python, I'm not sure how to make it easier. Compile an exe with a GUI?

The code is pretty simple/self contained, but definitely not the best organized thing.

I've only tested it in Firefox/ESPN. I put a sample chrome `manifest.json` but haven't tested it. Modifying it to use other platforms would involve changing the `const playerElements = document.querySelectorAll('.jsx-2093861861.pick__message-information .playerinfo__playername');` query in `content.js` to whatever those platforms use to identify pick information.