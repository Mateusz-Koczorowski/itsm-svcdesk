<!-- ai-generated: 75% - Claude drafted the comparison from both ledgers; I ran the second investigation and checked the verdicts against the snapshot -->

# Two investigators of lab4-rec-1

| | first (`ai-rca-eval.json`) | second (`ai-rca-eval-2.json`) |
|---|---|---|
| agent | course agent loop, the recorded investigation | course agent loop, run by me on the served snapshot |
| model | qwen3:4b-instruct (local) | gemini-flash-lite-latest (Google AI Studio, free tier) |
| transcript | `ai-rca/transcript.md` | `ai-rca/second/transcript.md` |
| hypotheses | 5: 0 correct, 1 partially correct, 4 hallucinated | 4: 1 correct, 3 partially correct, 0 hallucinated |

Both ran the same loop and the same MCP server against the same recording, so the difference is the model, and
how it was asked.

## Where they agreed

Both put the symptom in checkout: the first's H3 (PlaceOrder slower) and the second's H1 (checkout p95 up to
5,500 ms against 48 ms) are the same finding, and the snapshot proves both true (PlaceOrder p99 8.8 s at 05:07,
server p95 5.5 s at 05:05). Neither went further than the paging alert `ShopCheckoutSlow` with it; both are
partially correct because they locate the symptom and not its cause.

## Where they parted

- **Reading the data.** The first model read cumulative counters as rates and call counts as durations
  ("85 to 344 milliseconds"), and four of its five claims fell apart on one query each (H1, H2, H4, H5 hallucinated).
  The second used `rate(...[5m])` and `histogram_quantile` correctly, and every number it quoted was in the data;
  its one slip was a timestamp (5,500 ms "around 05:15Z" when the point was 05:05).
- **Inside or outside checkout.** The first blamed the product catalog (H2) and checkout's own
  `prepareOrderItemsAndShippingQuoteFromCart` span (H4), both false: GetProduct stayed at 34 ms and that span at
  48 ms. The second checked that same span, found it flat at 48 ms, and turned to checkout's outgoing HTTP POST
  calls, which did slow down (p95 9 to 94 ms, p99 to 7.3 s) - the right direction, towards shipping's ShipOrder
  (p99 8.2 s). It did not ask which POST target was slow, so it never named shipping.
- **Beyond the alerts.** Only the second found a second fault: email's p95 from 8 to 148 ms (its H4, correct). No
  alert named email, so this did not come from `alerts_at`. It is the visible side of the memory leak (email's
  container at 100.5 MB of 104.9 MB). Neither model looked at the ad service, whose GetAds errors (up to 12 %) are
  the third fault: they asked about latency because the page was about latency.
- **Noise.** The second's H2 (frontend p95 up to 62 ms) is true but adds nothing: a 20 ms rise that is checkout's
  delay seen from the frontend.

## Which one the data proved right

The second, on every point where they differ: its numbers re-execute on the snapshot, its direction (outbound
calls, not checkout's code) is where the fault was, and it found email. The cost was one failed run first: asked
the same question as the recording, with `[1m]` windows on one-minute data, it got empty results and concluded
there was no data. It needed to be told the scrape interval, a fact about the data, not a conclusion, while the
first model was never given that hint. Neither identified a flag, and neither would have found the ad failures
without a question about errors: an investigator only answers the question it is asked, so the alerts a team
writes decide what its AI will look for.
