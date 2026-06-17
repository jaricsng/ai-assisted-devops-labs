# Lab Reflection — [Your Name]

**Date:** <!-- fill in -->
**GitHub repo:** <!-- link to your repo -->

---

## 1. What I Built

<!-- One paragraph: describe the app and the architecture you implemented.
     Include the tech stack, the three-tier structure, and at least one design decision you made. -->

---

## 2. Where Claude Code Helped

<!-- Give 3 specific examples. For each, paste the prompt you used and describe
     what Claude Code produced. Was the output useful as-is, or did you revise it? -->

### Example 1 — Prompt:
> 

**What it produced:**

**Did you use it as-is?**

### Example 2 — Prompt:
> 

**What it produced:**

**Did you use it as-is?**

### Example 3 — Prompt:
> 

**What it produced:**

**Did you use it as-is?**

---

## 3. Where I Disagreed with Claude Code

<!-- At least 1 example where you overrode Claude Code's suggestion.
     What did it suggest? Why did you choose differently? -->

**What Claude Code suggested:**

**What I did instead and why:**

---

## 4. Security Finding I Wouldn't Have Caught Myself

<!-- Describe a finding from any security tool: /security-scan, /security-review,
     /check-secrets, /pen-test, /compliance-check, or the manual pen test script
     (pen-tests/manual-checks.sh). What was it? How did you fix it (or why did
     you accept the risk)? What would have happened if it had reached production?
     If all tools passed, describe which finding surprised you most when you learned
     what it was checking for. -->

**Finding (tool and severity):**

**What it meant in practice:**

**What I did about it:**

---

## 5. Observability: What I Learned

<!-- Describe your experience with the OTel → Prometheus → Jaeger → Grafana stack.
     Answer: what was the first thing you discovered by looking at traces that you
     couldn't have found from logs alone? -->

---

## 6. Load Testing: What the Numbers Revealed

<!-- Describe what you learned from running the k6 smoke, load, or spike test.
     What did the p95 latency or error rate tell you that you couldn't see from
     unit tests or manual testing? Did any threshold fail? If so, what was the
     root cause (DB query, pool exhaustion, slow middleware) and what did you
     change? If all thresholds passed, what was the most surprising metric? -->

**Scenario I ran (smoke / load / spike):**

**What the numbers showed:**

**What I changed (or why I accepted the result):**

---

## 7. Best Practice I'll Carry Forward

<!-- One concrete habit or technique you'll apply in your next project.
     It should be specific — "run /security-scan before every PR" is specific;
     "write more tests" is not. Include a concrete example of how you'd apply it. -->

---

## 8. What I'd Improve

<!-- One architectural or process decision you'd make differently if you started again.
     Why? What would you do instead? Consider your ADRs — is there a decision you'd
     revisit now that you've seen the full implementation and tested it under load? -->

---

*Word count target: 600–900 words across all sections.*
