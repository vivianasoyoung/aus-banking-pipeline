# Blog post outline — draft

Working title options (pick one):
- "Building an end-to-end banking data platform: the design decision that almost broke my fraud model"
- "Why I source ML labels from my streaming pipeline (and the leakage trap I nearly shipped)"
- "From four repos to one system: lessons building a DE/MLE portfolio"

Target length: 1,200–1,800 words. Audience: hiring managers + other DEs. Tone: honest,
specific, a little vulnerable about the bug. That honesty is what makes it memorable.

---

## 1. Hook (1 short paragraph)
Open with the bug, not the architecture. Something like:
> "My fraud model scored a perfect AUC of 1.00. I was thrilled for about ten minutes —
> until I realised that number was the symptom of a mistake, not a success."
Then promise the reader: here's the system I built, the trap I fell into, and what I learned.

## 2. The system in one diagram (2–3 paragraphs)
- Drop the cross-repo Mermaid diagram (you already have it).
- One sentence per repo: pipeline (ingest), dbt (transform), streaming (real-time fraud),
  feature-store (ML).
- State the design principle up front: **each repo does one job, and they connect through
  data, not code.**

## 3. The interesting decision: where do ML labels come from? (the heart — 4–6 paragraphs)
This is the part nobody else's portfolio has. Spend the most words here.
- Explain the naive approach: compute features from transactions, then label "high risk"
  using a rule on those same transactions.
- Show *why that's circular*: if the label is `max_amount > 5000 OR night_ratio > 0.3`,
  and you feed the model `max_amount` and `night_ratio`, it just re-derives the rule.
  → AUC = 1.00. The model learned nothing.
- The fix: labels come from an **independent signal** — the streaming fraud engine's
  `flagged_transactions` table. Features describe behaviour; labels come from a separate
  system's judgment. Now the task is genuinely predictive.
- Tie it back to the architecture: this is *why* the streaming repo and the feature-store
  repo are connected. The design isn't arbitrary — it enforces the separation.
- Bonus credibility: mention you wrote a regression test that fails if any feature column
  can trivially reconstruct the label, so the leakage can't sneak back in.

## 4. How I keep it honest: testing + CI (2–3 paragraphs)
- Each repo has CI. dbt runs `dbt build` + 43 data tests against a real Postgres on every push.
- Be honest: CI caught FOUR real bugs I'd missed — a broken mart reference, two syntax
  errors, an unused variable. Frame this as "CI earns its keep," not "I write buggy code."
- One screenshot of a green CI run.

## 5. What I'd do differently in production (2–3 paragraphs)
- Pull from REAL_WORLD_NOTES.md: in-memory velocity → Redis/Kafka Streams; rule-based
  scoring → calibrated model; schema registry; observability; exactly-once.
- This section signals you know the difference between a demo and production — exactly the
  judgment interviewers probe for.

## 6. Close (1 paragraph)
- Links to all four repos.
- One honest sentence on what you learned (the leakage lesson is the obvious one).
- Optional: what you'd build next.

---

## Assets to embed (gather these = the screenshot task)
- [ ] Cross-repo Mermaid diagram (have it)
- [ ] Airflow DAG green run
- [ ] Kafka UI showing transactions flowing
- [ ] MLflow experiment comparison (baseline vs RandomForest AUC)
- [ ] A green CI run
- [ ] dbt docs lineage graph (`dbt docs generate && dbt docs serve`)

## Where to publish
- LinkedIn article (most visible to recruiters) + link from each repo README.
- Optionally cross-post to dev.to or a personal site.
- Add the post link to the top of each repo's README under the cross-repo section.

## Tips
- Lead with the bug story; architecture diagrams alone are forgettable.
- Use real numbers (95k transactions, 500 accounts, 43 dbt tests, realistic AUC after the fix).
- Keep code snippets short — 5-10 lines max, just enough to show the leakage.
- End-to-end honesty (admitting the AUC=1.00 mistake) reads as senior, not weak.
