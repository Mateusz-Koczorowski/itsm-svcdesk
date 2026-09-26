---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 75% - Claude drafted from METRIC-SPEC.md and the practice log; the gaming examples are from my own experience -->

# Edge cases in the practice event log

Counts are what my own service reports for `fixtures/events-practice.jsonl` over the published window
(see `metrics.json`).

## E1 - clock skew produces a negative lead time

- What the log contains: three successful deployments ship a commit stamped after the deployment itself: DEP-0012 carries sha-0040 (14 minutes "in the future"), DEP-0024 carries sha-0094 (51 seconds) and DEP-0031 carries sha-0123 (13 minutes). The machines disagreed about the time; the code obviously existed before it was deployed.
- What a default definition would have done: either drop the pairs as invalid, which silently shrinks the sample and removes exactly the fastest deliveries, or keep the negative values, which pulls the median down with durations that cannot exist and, on a small team, can even produce a negative lead time on the dashboard.
- Why the rule is defensible: R-08 clamps to zero and still counts the pair, so the delivery is not lost and no impossible duration enters the median; the anomaly counter tells the reader that clocks are skewed, which is an operational problem worth fixing rather than hiding.

## E2 - a revert of a revert

- What the log contains: sha-0070 reverts sha-0069 (change CHG-0033), and sha-0071 reverts sha-0070, so the original change is back. Neither revert has a change_id of its own.
- What a default definition would have done: treat each commit as its own unit of work and report three changes where the team delivered one, inflating throughput and, in lead-time terms, measuring the revert commits from their own late timestamps instead of from when the work started.
- Why the rule is defensible: R-06 resolves every revert transitively to the change it undoes, so undoing and redoing work is visible as churn on one change and never rewarded as extra output; the reader of the dashboard sees one change that took longer, which is what happened.

## E3 - a hotfix that never touched `main`

- What the log contains: four successful production deployments (DEP-0006, DEP-0019, DEP-0028, DEP-0033) carry commits from `hotfix/*` branches that were never on main.
- What a default definition would have done: filter commits on `branch == "main"`, which drops exactly the urgent fixes, the ones deployed fastest under pressure, and makes lead time look slower and the recovery path invisible.
- Why the rule is defensible: R-09 measures what reached production, not what followed the branching policy; how code got there is a process question that belongs in a separate report, and the anomaly counter surfaces the policy bypass without distorting delivery numbers.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments with an empty commit list, two successful (DEP-0026, DEP-0032) and two failed (DEP-0043, DEP-0044), typically redeploys, config pushes or rollbacks.
- What a default definition would have done: drop them because they carry no change, which hides two failures from the change fail rate, or divide by an empty list somewhere and crash or report nonsense.
- Why the rule is defensible: R-10 keeps them where they matter - they were real deployments that could and did fail, so they count in frequency and in both instability denominators - and only exclude them from lead time, where there is genuinely nothing to measure.

## E5 - a deployment that failed and never recovered

- What the log contains: DEP-0015 failed on 7 September and its covering incident INC-0004 was opened but never resolved inside the log.
- What a default definition would have done: close it at the end of the window, inventing a recovery time, or drop it, which makes recovery look better precisely because the worst failure is missing.
- Why the rule is defensible: R-12 does not invent data: the open failure is excluded from the recovery median, counted separately so the reader knows it exists, and still counted as a failure by R-14. An unrecovered failure is the most important line on a reliability dashboard, not a rounding problem.

## E6 - overlapping incidents

- What the log contains: 11 incidents whose intervals intersect in 11 distinct pairs; several were open at the same time, and one of them (INC-0004) never resolved, so its interval runs to the end of the window and overlaps everything opened after it.
- What a default definition would have done: merge overlapping incidents into one outage, which undercounts failures, or sum incident durations, which double-counts wall-clock time and makes recovery look worse than any user experienced.
- Why the rule is defensible: R-13 measures recovery per failed deployment, from that deployment to the resolution of the incident that covers it, so each failure has one honest number; the overlap counter tells the reader that incidents pile up, which is a capacity signal in its own right.

## Gaming demonstration

I improved `change_lead_time_seconds_p50` by exploiting R-08. In `gaming/after.jsonl` I held back the last eight
successful base deployments (DEP-0030 to DEP-0042) into a single release after the window, on 24 September, and
added forty trivial one-commit changes, each deployed ten minutes after it was written. R-08 is a median over
(deployment, commit) pairs, so every commit weighs the same: forty ten-minute pairs drown the real ones. The
reported lead time drops from 375643 s to 237261 s, about 37 % better. Measured on the base work alone (R-21),
the number of real changes delivered in the window falls from 65 to 50, so delivery of the work that was already
there got clearly worse while the headline metric improved. As a side effect deployment frequency also rises,
from 2.0 to 3.52 per day, which would make the dashboard look even better.

I have seen the same mechanism in my own work as a QA engineer. When test automation coverage became a number
reported upwards, we were pushed to raise it as fast as possible; coverage went up, but many of the new tests
were shallow and checked little, so the metric improved while the safety net got weaker. The pattern is the
same each time: the metric counts units that are cheap to produce, so the cheapest way to move it is to produce
more cheap units, not to do the work better. For lead time the cheap unit is a small, low-risk commit: the
easiest way to hit a target like "median lead time under three days" is to ship many of those quickly and let
the large, risky changes wait for a release train, which is exactly what my `after.jsonl` does.

The incentive comes from above: clients and stakeholders want more delivered, and a manager has to show them a
number that proves it. That manager is rewarded, because the dashboard now reports faster delivery. Users and
the team pay for it: the changes that matter reach production later, eight of them land at once in a single
large release that is riskier and harder to roll back, and forty deployments of trivial changes add operational
noise without adding value. In my coverage example the bill came as shallow tests and technical debt; here it
comes as delay and concentrated risk. R-16 is what exposes the trick: when the checker strips my added commits
and counts only the real changes delivered, that number fell by almost a quarter.
