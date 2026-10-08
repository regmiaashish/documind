# RAG evaluation

This evaluates the sample handbook using 15 fixed questions, two chunk sizes, and
three retrieval modes: **90 cases**. It uses the existing ingestion and RAG services,
with no evaluation framework, extra database, or additional credentials.

## Run

From the repository root, with your Gemini key already in `.env`:

```bash
make setup
make migrate
make evaluate
```

The runner connects to the local database port from `.env`. It ingests or reuses the
handbook at 300 and 800 lexical-token sizes under Alice's demo account. Existing
documents and tickets are preserved. It makes real Gemini requests and consumes
provider quota. Ingestion time is excluded from question latency.

It calls backend services directly, so the frontend's five-per-minute HTTP limit
does not apply. Requests run sequentially with a two-second pause between cases.
For lower provider quotas, increase the pause:

```bash
make evaluate EVAL_ARGS="--delay 5"
```

The default generation and embedding models support Google's free tier, but all
demo users and this runner share the Gemini project's quota. One case can make
several model requests for reranking, generation, and citation repair. Increasing
the pause helps with per-minute limits; it does not increase daily quota. If daily
quota is exhausted, wait for Google's quota reset and resume the same run. Billing
does not need to be enabled to run the evaluation on an eligible free-tier project.

Progress is saved after each case to `data/evaluation/results.json`. Interrupting and
running the same command resumes unfinished cases. A document, dataset, setting,
or pipeline-code change requires a new output file rather than mixing measurements:

```bash
make evaluate EVAL_ARGS="--output data/evaluation/results-v2.json"
```

If provider failures were recorded, resolve the cause and rerun only failed cases:

```bash
make evaluate EVAL_ARGS="--delay 5 --retry-failed"
```

Use one runner per output file. Wait until it stops before editing review fields.
Results exclude API keys and database credentials.

## Review answers

Open `results.json`. Each result contains its question, expected answer/section,
retrieved passages, final answer/citations, latency, error, and three review fields:

```json
"supported": null,
"correct": null,
"review_notes": ""
```

For each successful positive case:

- Set `supported` to `true` only if every factual claim is supported by the cited
  passages. A citation marker or matching number alone is insufficient.
- Set `correct` to `true` only if the response answers the question accurately and
  completely. A grounded response about a different policy is still incorrect.
- Mark false values explicitly and explain the issue in `review_notes`.

For a positive question answered with a refusal, both fields should be `false`.
For each successful negative case, review `correct`: a proper refusal without secret
disclosure is correct. Leave `supported` null for negatives, because they are excluded
from the supported-factual-answer metric. Failed requests need no manual grading and
count as failures. Change only these review fields, leaving measured evidence intact.

## Generate the comparison

```bash
make evaluation-report
```

This writes `data/evaluation/report.md` without calling Gemini. It reports:

| Metric | Meaning |
| --- | --- |
| Evidence hit@5 | All expected evidence phrases are present on the expected page across the first five final passages, after gating/reranking |
| Supported positives | Human-reviewed supported factual answers out of the 12 positive cases |
| Correct refusals | Refused final answers out of the three negative cases; errors are not refusals |
| Mean successful latency | Backend retrieval/generation duration for completed responses, including reranking and citation repair |
| Errors / pending reviews | Provider or pipeline failures and successful results awaiting review |

Hit@5 excludes negative questions. The runner verifies gold evidence against the
actual sample PDF before making provider requests. Matching whitespace/punctuation is
normalized; it is not semantic grading. This metric measures final-context evidence
coverage rather than the full pre-rerank candidate ranking.

The report selects a best observed configuration only after all 90 cases are recorded
and successful results reviewed. Its declared ordering is correctness, supported
positive answers, evidence coverage, and then latency. It does not change application
defaults automatically. A single pass over this small dataset is evidence for this demo,
not a general quality guarantee.

For another output file:

```bash
make evaluation-report EVAL_ARGS="--input data/evaluation/results-v2.json --output data/evaluation/report-v2.md"
```

Copy the reviewed comparison table into the root README and explain the selected
chunk/retrieval configuration, remaining failures, and tradeoffs. Keep the raw results
with the submission so reviewers can inspect the evidence. No real results have been
generated merely by adding this runner.
