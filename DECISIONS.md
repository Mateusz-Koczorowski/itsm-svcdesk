---
svcdesk_decisions:
  C1: wallclock      # wallclock | business
  C2: immutable      # reopen | immutable
  C3: matrix         # matrix | vip
---
<!-- ai-generated: 60% - Claude drafted the prose from my choices and arguments; decisions and final wording are mine -->

# Decisions

## C1 - SLA clock for P1

**Decision:** Both P1 targets (acknowledge within 15 minutes, resolve within 4 hours) run on the wall clock, around the clock. P2 to P4 keep the business-hours clock. We keep R-14 and reject R-13 only for P1: a P1 is never paused.

**Rejected alternative:** Business-hours clock for P1 as well (R-13 for every priority). A P1 raised on Friday at 17:00 would then be due for acknowledgement on Monday at 08:15 and would show as paused all weekend.

**Reason:** A P1 is by definition impact 1 and urgency 1: the whole organisation is affected and work has stopped. R-14 was written as an explicit exception for exactly this case, with the Friday-evening example, so it is the more specific requirement. A clock that says "on time" while all three offices are down for a weekend would make the SLA report meaningless for the one class of incident it matters most for. The cost is real: someone must be reachable outside 08:00-16:00, so we need an on-call rota for P1 only; P2 to P4 still wait for business hours.

**Service owner:** The Head of IT Operations (owner of the service desk service), because this decision commits the IT team to an on-call rota and its budget; the desk lead cannot sign that alone.

**Customer outcome:** When the whole organisation is down outside office hours, someone acknowledges within 15 minutes and works toward a fix within 4 hours instead of on Monday; staff can start the next working day on a working system.

## C2 - Closed tickets and reopening

**Decision:** A closed ticket is immutable. Reopen works only from `resolved`, within 7 days of `resolved_at`; reopening a closed ticket answers 409 at any age, and further work goes into a new ticket with `related_to` pointing at the closed one. We keep R-09 and reject the "or closed" part of R-10.

**Rejected alternative:** Allow reopening a closed ticket within 7 days of its closure (R-10 in full), returning it to `in_progress` and clearing `closed_at`.

**Reason:** Per R-07 a ticket is closed only after the reporter has confirmed the fix, and the reporter already has 7 days in `resolved` to say it did not work. Reopening after that confirmation rewrites a closure everyone agreed on, so closure counts and resolution times in the reports stop being stable, which is what the desk asked us to prevent. A new linked ticket keeps the history honest: the first fix and the recurrence are both visible and measured separately.

**Service owner:** The Service Desk manager, who owns the ticket lifecycle and the Monday report and answers for whether its closure figures can be trusted.

**Customer outcome:** A reporter whose problem returns after closure gets a fresh ticket with its own SLA clock and a link to the earlier one, instead of a reopened ticket whose original deadline has already passed; management gets closure numbers that never change after the fact.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority comes from the impact and urgency matrix only. `reporter.vip` is stored and returned with the ticket, but never changes its priority: impact 3, urgency 3 from a VIP is P4. We keep R-05 and reject R-06.

**Rejected alternative:** Raise every VIP ticket at P3 or P4 to P2 after the matrix (R-06), so executives always get a 1-hour acknowledgement target.

**Reason:** Priority is the desk's statement of business impact, and the SLA targets and the queue order follow from it. A VIP bump would put one executive's cosmetic problem ahead of a team whose work is degraded (P3), and would spend P2 capacity on tickets that do not stop anyone's work. It would also make the priority figures in the reports reflect job titles rather than impact. The VIP flag stays on the ticket, so the desk can still see who reported it and give courtesy attention without changing the SLA.

**Service owner:** The Service Desk manager, who owns the priority matrix and the queue policy; changing who jumps the queue is a service-policy decision for that role, agreed with the business.

**Customer outcome:** Every reporter, VIP or not, gets a priority and a deadline that match how much work is actually stopped, so teams with degraded work are not pushed back by low-impact executive requests.
