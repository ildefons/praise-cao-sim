# WP5a feasibility freeze — 26 November 2026

Decision: PASS for nominal prediction graph trajectory accounting; insufficient evidence for comprehensive wall-clock or CPU-hour accounting. User agreed to defer manuscript integration and proceed to WP3a.

Read-only local inventory (d17b21a): 44/84 method-condition pairs have candidate timing markers, with coverage 0/12 each for M1, M2, M3_FULL343; 10/12 each for original Top14/Top1; 12/12 each for fixed-CV Top14/Top1. Candidate markers require provenance checks.

Trajectory diagnostic script: 694a0d4. Nominal per-action costs: M1 100, M2 2700, each of the five remaining methods 1400 graph trajectories. Excludes WB, shared preparation, overhead and cache effects. Previously reported diagnostic covers six nested policies, 230400 actions and 37440 terminal decisions. Top2 action histories unavailable. Reported sustained mean-regret <=0.002 comparison: adaptive two-stage KG nominal workload reductions versus Random 40.9% historical and 48.8% fresh, versus Balanced 29.8% and 45.0%. These are descriptive evaluation-count checkpoint comparisons, not fixed trajectory-budget experiments or total computational savings. Preserve the underlying results for WP5b; independently recheck outputs and provenance before manuscript integration. No acquisition changes or new simulation authorized.

Next: WP3a external CMMS benchmark feasibility and protocol design, before execution. WP1/WP2 remain frozen.
