# Phase-5 V2 M2 confirmation-reference implementation clarification

Date: 2026-10-05

This note records an implementation-level clarification before any Phase-5 M2
candidate has been generated or evaluated.

The frozen Phase-5 method contract requires the same A4 GP/straddle procedure,
a confirmation compatibility ratio of 1.25, five provisional members, and three
final members. The historical frozen A4 procedure defines confirmation
compatibility relative to the **previously frozen provider-specific best
100-trajectory confirmation MSE**, and does not recompute that reference from
the newly confirmed A4 candidates.

Phase 5 deliberately contains no additional pre-A4 confirmation stage. Before
M2 starts, the only provider-specific 100-trajectory confirmation result already
frozen under the new world's public I1 is the M1-v2 shortlist confirmation. M1
selects the lowest confirmation-MSE member of that frozen shortlist.
Consequently, for each Phase-5 provider world and provider, the A4
"previous-best confirmed MSE" is instantiated as the already-frozen M1 selected
surrogate's confirmation MSE.

Therefore the Phase-5 M2 confirmation gate is

    candidate_confirmation_MSE
        <= 1.25 * frozen_M1_selected_confirmation_MSE.

This mapping is non-adaptive and is fixed before any Phase-5 M2 confirmation
outcome is observed. It does not inspect Step-0 WB values, graph predictions,
graph white-box outcomes, or hidden provider parameters.

The remainder of the frozen A4 procedure is unchanged:

1. search compatibility uses the 1.25 ratio to the frozen best final-domain M1
   search MSE on the 25-trajectory search CRN bank;
2. the 48-point nonadaptive LHS and 48 new GP/straddle evaluations are performed
   in the final declared M1 domain;
3. provisional member 1 is the lowest observed local search MSE and members
   2--5 are selected by greedy maximin distance in normalized
   (log-mu, log-kappa, CV), with the frozen tie breaks;
4. all five provisional members are confirmed on the frozen 100-trajectory
   confirmation bank;
5. the first three passing members in the precomputed provisional order are
   retained;
6. those three are replayed on the frozen independent 100-trajectory replay
   bank for diagnostics only; replay cannot change selection.

This note does not alter the Phase-5 V2 scientific design. It makes explicit the
unique mapping of the already-frozen A4 confirmation-reference semantics onto
the Phase-5 stage inventory, which intentionally contains no extra pre-A4
confirmation stage.
