# 26 — Matchups and weather are worth about a point, at best

**Confidence: High** (24 seasons of games for the ratings, 36,000 player-weeks for the weekly tests)

## TL;DR

We tested whether team strength, defensive matchups, weather, and receiver-vs-cornerback data improve fantasy projections. Season-long: nothing helps — team quality changes too fast year to year. Week to week: knowing the opponent is worth about one point at QB and RB and zero at WR, and the Vegas line already prices most of it before you ever check a matchup chart.

## The season-long test

We built our own team ratings from 24 years of games; they track the Vegas point spreads closely, so they're doing their job. It doesn't matter. Nothing predicts a team's scoring next season better than its plain points per game last season, and even that is a loose guide. Adding team ratings to [our projection model](#/blog/25-player-model) changed its accuracy by exactly nothing — a player's own production already carries his team's context.

## Week to week: one point, mostly at QB

Across 36,246 player-weeks, the one genuine weekly upgrade was usage-based expected points — what a player's carries and targets *should* have scored. That's [buy volume, not efficiency](#/blog/17-buy-targets-not-efficiency) again at weekly scale. On top of that, opponent quality and the betting line add value only at QB — fittingly, [the position our league streams](#/blog/06-qb-timing). Between two comparable players, a matchup-based start/sit call is a coin flip with a one-point thumb on the scale.

Weather follows the same pattern. Wind is what bites: 15+ mph costs QBs almost two points and receivers about half a point, while cold alone is mild and running backs shrug it all off. The snow-game folklore, stated correctly: bad weather doesn't make RBs better, it makes everyone else worse. But adding weather to the model gained nothing, because by the time you see the forecast, the implied total — the score Vegas expects a team to put up — has already moved.

## The WR-vs-cornerback report failed its own test

We tested the receiver-versus-cornerback idea three ways, including scoring a full week of a commercial matchup report against actual results. Their matchup grade had zero relationship with real scoring — their "bad matchup" receivers actually outscored their "good matchup" ones that week — and the best predictor on their own page was simply how many routes a receiver runs. A defense's supposedly weak left side doesn't even persist within a single season. Volume and recent form are signal; matchup talk is noise.

---

*The full write-up, with every table and how to reproduce it: [findings/26-team-environment.md](https://github.com/Zinkelburger/Fantasy-Football-Tool/blob/main/engine/league-sim/findings/26-team-environment.md)*
