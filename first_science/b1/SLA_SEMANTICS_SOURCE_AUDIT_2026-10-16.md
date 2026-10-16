# B1 Step 2.3a: SLA estimand and deadline semantics, source-level audit

**Date:** 2026-10-16  
**Status:** SOURCE-CONSISTENT FOR INSPECTED MAINLINE IMPLEMENTATIONS. This is a static code inspection, not raw-ledger replay or a proof for every historical/experimental script.

## Manuscript source

Historical manuscript v11_45, Eq. (2) p2 and SLA discussion §3.1 p4:

`sigma_G(A,H;rho)=Pr[f_G(A,H)>=rho]`

where `f_G` is the cumulative fraction of SLA-compliant **decided** requests by horizon H; unresolved requests excluded; zero decided treated as compliant.

## Repository source chain

1. `phase1/sla_compliance_analysis.py::build_request_sla_decision_table`
   - Request latency deadline is `emission + latency_threshold`.
   - If completion <= deadline, decision at completion; then cost/quality acceptance is evaluated.
   - Otherwise decision at deadline, with latency-failure status.
   - Decisions after simulation stop remain unresolved. Source lines near 101–115.
2. `phase1/sla_compliance_analysis.py::_cumulative_compliance_after_decisions`
   - Filter for known decision time <= requested H.
   - If zero decisions, returns the declared `zero_decision_compliance=1.0`; else compliant count divided by decided count. Source lines near 175–184.
3. `phase1/sla_compliance_analysis.py::calculate_trajectory_cumulative_sla_curve`
   - SLA pass indicator for each horizon: `compliance_fraction + EVENT_TOLERANCE >= rho`. Source lines near 209–228.
4. `phase3/run_m1_graph_prediction_v2.py::build_empirical_graph_sigma_curve`
   - Uses the same `calculate_empirical_sla_sigma_from_ledgers`, with `SlaComplianceDefinition(...zero_decision_compliance=1.0)`; employed for graph M1 and graph WB in Phase3.
5. `phase5/run_phase5_final_wb_v3b_fullsupport.py`
   - Explicitly uses `calculate_empirical_sla_sigma_from_ledgers` with graph `A_G_l_max/A_G_c_max/A_G_q_min` and zero-decision compliance 1.0. Source around its per-query white-box construction.
6. `phase5/run_phase5_graph_prediction_v3b_fullsupport.py`
   - Imports `build_empirical_graph_sigma_curve` from Phase3 as graph prediction curve extractor.

**Audit result:** The Eq. (2) semantic claim is supported by the inspected source chain, including missed-deadline-as-decided-failure rather than dropping late requests, and zero-decided compliance of 1.0.

**Important distinction:** The event accounting code explicitly allows the cumulative-compliance status to change from failure back to pass after subsequent compliant requests. In `phase1/sla_compliance_analysis.py::calculate_exact_trajectory_sla_compliance_area` the docstring notes trajectories can recover from noncompliance. This `sigma_G` is therefore a **horizon-specific SLA satisfaction probability**, not first-passage/absorbing survival. Avoid assuming monotonicity in H or borrowing first-passage survival bounds/results without changing the estimand and labeling a new interface.

## Remaining work

- This audit does **not** reconstruct archived per-trajectory WB and provider outcomes from raw simulator request ledgers.
- The public I1 region-generation semantics, Step0 query construction, and every historical variant's status must be cross-checked separately in substeps 2.3b/2.4.
- Numerically correct pointwise `sigma_G` does not guarantee predictive accuracy of a reconstructed graph model. Keep the distinction from the Step1 verification.
- Uncertainty and admission-guarantee terminology remain pending a separate detailed math/source audit.

**Editorial disposition:** Retain original Eq. (2), preserve `rho_region` vs `rho_query` separation, improve explanatory terminology; do **not** replace the target by first-violation survival in B1.
