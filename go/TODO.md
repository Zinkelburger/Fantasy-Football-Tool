AI:
- Update system/user prompt to suck less (rn responses appear with --start player-- output, etc.)
- Add integration to Claude
- Run query automatically, a few picks before you, as it can take a bit for the reply to come in
- Stream the GPT responsess
- test local ollama

UI:
- Increase settings menu: Different formats (PPR, 0.5PPR)
- Allow filtering WR, RB, etc. Position types.
- Allow searching for a player, searchbar (not fuzzy match)
- Hotkey to open the files on disk, may be unclear where to find the player & rankings file to modify

Platforms:
- Sleeper
- Yahoo

Tutorials:
- create tutorials on how to use the tool, how to get an OpenAI api key

Extraneous/impractical/beyond my abilities:
- Potential issue if players have the same name without suffixes (ensure consistent handling, some other solution besides removing them)
- Distribution of outcomes for each players. Standard deviation, median, mean for all players. Graph you can see if you hover over the player. (how to get the data bro idk)
- Calculate player value with the "value over replacement" algorithm, some way to gague opporunity, or simulate outcomes (if you're bad at math). To see when WR value, RB value is likely to present itself.
- An "upside/ceiling" and "risk" score.
- highlight interesting players in green, uninteresting ones in red, neutral for others
(green can be ChatGPT's 3 positive suggestions, red can be positions you've already filled)
