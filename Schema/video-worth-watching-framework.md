# Video Worth Watching Framework

A video is worth watching only if it beats the opportunity cost of attention.

The working definition:

> This video is likely to produce a meaningful change in my thinking, behavior, taste, judgment, skill, or principles that I could not get faster elsewhere.

This is a sharper frame than asking whether a video is merely interesting.

## Core Criteria

### Relevance

Does this connect to something I currently care about?

Examples:

- Career
- Health
- Faith, culture, and relationships
- Rejection therapy
- Communication and storytelling
- Business, product, and AI
- Personal discipline
- Immigration or life planning

If relevance is low, the video needs to be exceptionally unique to justify watching.

### Actionability

Will this change what I do?

Good signs:

- It gives a concrete practice, habit, decision rule, script, framework, or experiment.
- It solves a live problem.
- It helps me take action this week.

Weak sign:

- It is intellectually stimulating but has no behavioral output.

### Novelty

Is there something here I probably do not already know?

A video can be relevant but redundant. Redundancy matters because I already consume a lot.

Ask:

> Is this likely to add a new distinction, principle, example, model, or counterargument?

### Credibility

Is the creator likely to know what they are talking about?

Signals:

- First-hand experience
- Strong track record
- Clear reasoning
- Specific claims
- Demonstrated results
- Acknowledges tradeoffs

Red flags:

- Overconfident universal advice
- Vague motivational language
- No examples
- Clickbait framing
- Selling a worldview without evidence

### Density

How much useful signal is there per minute?

A three-hour podcast can be worth it if dense and relevant. A twelve-minute video can be worthless if padded.

Useful question:

> Can I probably get 80% of the value from a summary, transcript search, or skimming?

### Timeliness

Does this matter now?

Some videos are good but not for this season. Those should become:

```yaml
decision: later
```

Not everything valuable deserves current attention.

### Personal Resonance

Does this connect to who I am becoming?

Some content may not be productive in a narrow sense, but may still feed:

- Courage
- Social risk-taking
- Storytelling
- Comedy
- Theater
- Identity formation
- Moral imagination
- Taste

Those can be valid reasons to watch.

## Watching Vs Processing

Worth watching and worth processing are different decisions.

A video can be:

- Worth watching, not worth saving.
- Worth saving, not worth watching fully.
- Worth processing, not worth watching.
- Worth ignoring.

Decision meanings:

- `watch`: emotionally or personally valuable, but not necessarily knowledge-base dense.
- `skim`: likely useful, but only parts matter.
- `process`: high-value knowledge source worth converting into notes.
- `skip`: low expected value.
- `later`: maybe valuable, but wrong timing.

Consumption is tracked separately from the triage decision:

```yaml
consumption_status: unwatched | skimmed | watched | abandoned
consumed_at: YYYY-MM-DD
```

Keep `consumption_status: unwatched` and `consumed_at:` blank until Rami personally consumes or abandons the video. This keeps the triage judgment separate from actual attention spent.

## Expected Value Rubric

Do not ask only whether the video is good. Score expected value:

```text
expected_value =
  relevance
+ actionability
+ novelty
+ credibility
+ density
+ personal_resonance
- redundancy
- time_cost
- clickbait_risk
```

This does not need to become rigid math. The model should produce a judgment with reasons.

Practical rubric:

```yaml
relevance_score: 1-5
actionability_score: 1-5
novelty_score: 1-5
credibility_score: 1-5
density_score: 1-5
personal_resonance_score: 1-5
time_cost: low | medium | high
redundancy_risk: low | medium | high
clickbait_risk: low | medium | high
combined_score: 0-100
decision: skip | watch | skim | process | later
triage_reason: ""
expected_gain: ""
```

## Key Question

For each video, the AI should answer:

> What would I realistically gain from this video, and is that gain worth the time compared to my current goals?

Then force one decision:

- `skip`
- `watch`
- `skim`
- `process`
- `later`

## Strongest Principle

Optimize for behavior change, not knowledge accumulation.

A video is most worth watching when it produces one of these outputs:

- A decision I will make differently
- A habit I will try
- A story I can tell
- A skill I can practice
- A belief I should revise
- A framework I can reuse
- A conversation I can have
- A creative idea I can adapt

If the video does not plausibly produce one of those, it is probably entertainment or passive consumption. That is not always bad, but it should not pretend to be learning.
