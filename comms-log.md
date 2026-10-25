---
lab4_comms:
  awareness: 2026-10-12T05:15:00Z
  detection: 2026-10-12T05:06:19Z
  classification: 2026-10-12T06:00:00Z
  nis2:
    early_warning_due: 2026-10-13T05:15:00Z
    notification_due: 2026-10-15T05:15:00Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  ksc:
    early_warning_due: 2026-10-13T05:06:19Z
    notification_due: 2026-10-15T05:06:19Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  dora:
    initial_due: 2026-10-12T10:00:00Z
    initial_sent: 2026-10-12T08:30:00Z
    intermediate_due: 2026-10-15T08:30:00Z
    intermediate_sent: 2026-10-14T12:00:00Z
    final_due: 2026-11-14T12:00:00Z
  log:
    - {at: 2026-10-12T08:30:00Z, to: the financial supervisor (KNF), what: DORA initial notification of a major ICT-related incident}
    - {at: 2026-10-12T10:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-13T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-14T12:00:00Z, to: the financial supervisor (KNF), what: DORA intermediate report}
---
<!-- ai-generated: 70% - Claude drafted the file and computed the deadlines; I chose the three instants and the sending times -->

# Communications log: the regulators' clocks

The shop is treated as an entity that NIS2, the Polish KSC act and DORA all apply to; the incident of 12 October
2026 (recording lab4-rec-1, ticket 3ba75e92-1b55-483b-a69e-6097c02b182c) is taken as significant under the first
two and major under the third. Every instant is UTC. 12 October 2026 was a Monday.

## The three instants you defend

**Detection (KSC), 05:06:19Z.** KSC counts "od momentu jego wykrycia", from the moment of detection, and the
moment our monitoring detected the fault is the moment the P1 alert `ShopCheckoutSlow` started firing: the same
instant as the postmortem's detection. Before it nothing had told anyone; after it the pager had the page.

**Awareness (NIS2), 05:15:00Z.** NIS2 counts from becoming aware of a *significant* incident, which is a judgement,
not an alert. At 05:06:56Z the on-call acknowledged the ticket and knew checkout was slow; by 05:15 they also knew
that ads had been failing for about ten minutes, that orders had taken up to 9 seconds for nine minutes, that the
email service had come within 5 % of its memory limit, and that all three had started together at 05:01 on a
configuration change. A customer-facing purchase path degraded together with two other services is what makes it
significant, and 05:15 is when that picture was complete. Choosing a later instant would only buy time on paper.

**Classification (DORA), 06:00:00Z.** Classifying an incident as major under DORA means running it through the
criteria of the delegated regulation (clients affected, duration, critical services, data), which needs the
incident manager and the business owner of checkout. Half an hour after the incident ended, at the start of the
day shift, is when that decision was made: checkout is a critical service and every customer who placed an order
in those nine minutes was affected.

## The deadlines

| clock | rule | due |
|---|---|---|
| NIS2 early warning | awareness + 24 h | 2026-10-13T05:15:00Z |
| NIS2 notification | awareness + 72 h | 2026-10-15T05:15:00Z |
| NIS2 final report | one month after the notification sent 2026-10-13T09:00:00Z | 2026-11-13T09:00:00Z |
| KSC early warning | detection + 24 h | 2026-10-13T05:06:19Z |
| KSC notification | detection + 72 h | 2026-10-15T05:06:19Z |
| KSC final report | one month after the notification sent 2026-10-13T09:00:00Z | 2026-11-13T09:00:00Z |
| DORA initial | classification + 4 h (10:00Z), earlier than awareness + 24 h (13 Oct 05:15Z) | 2026-10-12T10:00:00Z |
| DORA intermediate | initial sent 08:30Z + 72 h | 2026-10-15T08:30:00Z |
| DORA final | one month after the intermediate sent 2026-10-14T12:00:00Z | 2026-11-14T12:00:00Z |

The tightest clock is DORA's: four hours from the classification, so the initial notification goes first, before
anything to the CSIRT. KSC's clock starts 8 minutes 41 seconds earlier than NIS2's, so for the shared CSIRT reports
the KSC deadlines bind.

## The log

| when (UTC) | to | what | which clock it answers |
|---|---|---|---|
| 2026-10-12T08:30:00Z | the financial supervisor (KNF) | DORA initial notification: major incident, checkout degraded 05:01-05:10, service restored | DORA initial, due 10:00Z, sent 1 h 30 min early |
| 2026-10-12T10:00:00Z | the CSIRT | NIS2 and KSC early warning: significant incident, cause a configuration change, no sign of malicious action, no cross-border impact known | NIS2 and KSC early warnings, due 13 Oct 05:06:19Z (KSC binds) |
| 2026-10-13T09:00:00Z | the CSIRT | NIS2 and KSC incident notification: impact (slow orders, failed ads, email memory), root cause (three feature flags), the flags switched off | NIS2 and KSC notifications, due 15 Oct 05:06:19Z (KSC binds); starts the one-month clock of the final report |
| 2026-10-14T12:00:00Z | the financial supervisor (KNF) | DORA intermediate report: root cause, actions ITSM-101 to ITSM-104 | DORA intermediate, due 15 Oct 08:30Z; starts the one-month clock of the final report |

Still to send: the NIS2 and KSC final reports by 2026-11-13T09:00:00Z and the DORA final report by
2026-11-14T12:00:00Z, each with the postmortem's root cause and the status of its action items.
