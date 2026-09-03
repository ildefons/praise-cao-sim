# Phase-2 M0: topology-aware SLA contract composition

M0 is the first composition method evaluated with the minimal I1 provider cards. Phase 1 remains the frozen Step-0 benchmark; M0 consumes only the public graph/topology contract, deterministic fixed-stage parameters, the frozen global diagnostic AR, and I1 cards.

## Why there is no generic provider L/C/Q grid in the first pilot

The three meaningful top-level ARs were deliberately frozen in Phase 1 so that different `tau=(I,M)` technologies can be evaluated on the same nondegenerate diagnostic problems. For the first M0 pilot, a generic provider-local `(l_i,c_i,q_i)` grid is therefore unnecessary.

For each frozen global diagnostic cell

`A_G = {L_G <= l_G, C_G <= c_G, Q_G >= q_G}`

M0 derives exactly one sufficient local boundary for each ProviderA/B/C. Those exact local points become the I1 card boundaries used by both M0 and M1 for that diagnostic cell.

## Frozen first-anchor boundary algebra

For

`Fpre -> ParAll(A,B,C) -> Fpost`,

M0 uses

- latency: `L_G = L_common + max_i(L_branch_network_i + L_i)`;
- cost: `C_G = C_fixed + sum_i C_i`;
- quality: `Q_G = min(Q_fixed,Q_A,Q_B,Q_C)`.

The current public Phase-1 configuration gives deterministic service times

- `Fpre = 0.005 s`;
- `Fpost = 0.005 s`;

and current YAFS single-link latency

`message.bytes / (BW*1e6) + PR = 0.001001 s`

for the 1000-byte, 1000-Mbps, PR=0.001 links.

Thus the algebraic common latency term excluding the provider ingress link is `0.012002 s`; each branch ingress contributes another `0.001001 s`, giving `0.013003 s` total non-provider latency in the simple no-post-queue algebra. Deterministic Fpre/Fpost request execution cost is `C_fixed=0.03`.

For the first symmetric low-information policy:

- `l_i = l_G - 0.013003` for every provider;
- `c_i = (c_G - 0.03)/3` for every provider;
- `q_i = q_G`.

The actual runner must read the full-precision Phase-1 selected manifest rather than the rounded paper-facing values above.

## SLA error-budget decomposition

Global Phase-1 SLA requirement:

`rho_G=0.95`, hence `epsilon_G=0.05`.

First M0 allocation:

`epsilon_i = epsilon_G/3 = 0.016666666666666666`

and

`rho_i = 0.9833333333333333`.

This is separate from the L/C/Q budget decomposition.

## Probability composition

For the deliberately independent provider anchor,

`sigma_M0(H) = product_i sigma_i(A_i,H;rho_i)`.

The product is interpreted as the probability of the sufficient conjunction of local SLA events. It is a lower-bound certificate for the global SLA only when all of the following are true:

1. the local L/C/Q conjunction is request-level sufficient for the frozen global AR;
2. local cumulative SLA fractions and the global cumulative fraction refer to an aligned set of logical root requests at the horizon being certified;
3. the local SLA-compliance events are independent in the anchor world;
4. no omitted latency contribution, such as stochastic queueing in the nominally deterministic post stage, breaks the declared boundary algebra.

The pure counting theorem is simple: on one common aligned request set, if each provider has violation fraction at most `epsilon_i`, then the fraction of requests failing at least one provider is at most `sum_i epsilon_i <= epsilon_G`. Therefore the all-provider sufficient conjunction has compliance fraction at least `rho_G`.

The horizon/request-set alignment and post-stage latency assumptions must be audited on the real anchor before the empirical M0 curve is labelled a formal certificate. If they fail, that is a scientific finding about the limits of this minimal M0 rather than a reason to alter Phase 1.

## Files

- `config_phase2_m0_v1.json`: first M0 method contract.
- `m0_contract_composition.py`: boundary decomposition, aligned-request counting certificate, and independent I1 probability composition.
- `test_m0_contract_composition.py`: simulator-independent hand-checkable tests.

## Validation

Starting in `~/praise/praise-cao-sim/first_science/phase2`:

```bash
python test_m0_contract_composition.py
```

Expected:

```text
PHASE2_M0_CONTRACT_COMPOSITION_TESTS_PASS
```

After this passes, the next step is not a parameter search. It is an anchor-specific audit/extraction step: read the full-precision three frozen Phase-1 ARs, derive their nine exact local I1 boundaries, and verify the real request-level/horizon alignment assumptions needed by M0.
