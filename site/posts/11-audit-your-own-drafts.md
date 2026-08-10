# 11 — Grading your own drafts: the audit that found nothing

**Confidence: High** (the null is solid; the sample is small and we say so)

## TL;DR

You can export your league, replay every draft, and check each team
against the rules the rest of this site is built on. We built that
audit and ran it on 72 team-seasons. **It found nothing.** Five of six
rules came back inside the noise, and the sixth pointed the wrong way.
That is not a reason to throw out the rules — it is a lesson about what
your own league data can and cannot answer.

## What we tried

Take six rules that other findings settled. For every team in every
draft, check whether that team broke the rule, then compare how much
its draft returned. "Returned" means the points that drafted roster
would score with a perfect lineup every week — a generous yardstick,
but the same one for everybody, and it ignores waivers and lineup calls
so it grades the draft alone.

| Rule broken | Teams that broke it | Did their draft return more or less? |
|---|---|---|
| Tight end taken in rounds 5–9 | 65% | **More**, and not by chance |
| First quarterback after round 5 | 44% | Slightly less — inside the noise |
| Paid above market on average | 40% | Slightly less — inside the noise |
| Fewer than 2 RBs in rounds 1–4 | 35% | Slightly more — inside the noise |
| Drafted a second tight end | 35% | No difference |
| More receivers than running backs | 56% | Slightly more — inside the noise |

Drafting a pile of receivers — the thing we elsewhere call the costliest
plan we've tested — showed no penalty at all past five of them.

## Why it found nothing

**The measuring stick is too blunt.** A draft haul adds up sixteen
picks. Every rule in that table is about *one* pick. The tight-end rule
was established by comparing the tight end to the receiver or running
back taken at the very same pick — that comparison holds everything
else still. A whole-roster total can't: a manager who wins rounds 1–4
has a big haul no matter what he does at tight end in round 6.

**Good drafters break rules at good moments.** This is the trap. We hit
it before, in [finding 36](#/blog/36-draft-order) — "late running backs
win" looked real in observed drafts and vanished the second the
simulator *forced* teams to wait. Of course it did: good managers take
a late running back when a good one is sitting there. Same disease
here. Look at when teams took their first tight end:

| First tight end taken | Teams | Draft return |
|---|---|---|
| Rounds 1–4 | 17 | Below average |
| Rounds 5–9 | 47 | **Above average** |
| Round 10 or later | 8 | Well below average |

Read that as advice and it says "take your tight end in the dead zone."
Read it honestly and it says something duller: managers who spent an
early pick on a tight end had less left for everything else, and
managers who ignored the position until round 10 weren't paying much
attention generally. The middle is simply where ordinary drafting
lives, and ordinary beats both of those. The actual question — what
that same pick would have bought at another position — isn't in this
table at all.

**Seventy-two is a small number.** The margins of error here are wide
enough to hide every effect the simulations measure.

## What your league data *is* good for

Check whether you **followed** a rule, not whether the rule is true.

Your export answers the first question exactly and for free. The second
question needs a test that holds everything else still, and those live
in the findings the rules came from.

This matters most in the season a broken rule pays off. Take your tight
end in round 5, land the second-best tight end in football, and both
you and the audit above will call it vindication. You'd both be wrong
the same way: one good result from a bucket that hits 30% of the time
tells you nothing about the bucket.

Which leaves self-auditing one narrow, real use — **it catches
habits.** Breaking a rule once is noise. Breaking the same rule three
drafts running is a habit, and the finding that rule came from is where
the evidence about that habit lives.

## Run it yourself

`analysis/draft_leaks.py` in the engine takes ESPN league exports and
prints the table above for your league. Every team is anonymous in the
output.
