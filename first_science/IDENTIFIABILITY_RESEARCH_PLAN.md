# PRAISE identifiability feasibility plan

Branch: praise-identifiability-feasibility, based on caise-posthoc-mechanism-audit.

## Scientific target
Determine the minimum provider-local information required to identify horizon-dependent composed survival or an SLA admission decision. Separate (a) exact population identifiability, (b) finite-sample uncertainty and (c) computational inference error. Fix an allowed menu of disclosures and cost model before making any minimality claim.

## Existing frozen experimental track
P4/G_SEQPAR, 555 evaluated points and six interface/reconstruction variants. Overall MAE: I1STRONG .091781, I2AFS .094754, I2b-v1 .102096, I2b-v2 .157305, I2b-v3 .094294 and I2b-v4 .108539. Known-provider control MAE .027281; factorial provider substitutions show nonadditive effects. True-parameter oracle objective beats existing search candidates for both evaluated I2b objectives on all providers. The 54-candidate alignment audit shows inconsistent parameter/behavior/graph correlations. None proves I2 structural insufficiency. All existing results and settings must be archived and not overwritten.

## Research gates
G0 PRESERVE: SHA256 inventory and backed-up archive of phase3/4/5/6 results, manifests, figures and configurations. Record Git SHA, environment and data sizes. The code branch alone does NOT preserve local output. Verify an independent second copy.

G1 DEFINE: exact population I1, I2a, I2b observation operators and sampling kernels, generating family, graph semantics, dependence assumptions, eligible additional provider-local disclosures and disclosure costs. Stop until ambiguities are resolved.

G2 THEORY: characterize observational equivalence and functional identifiability for first-violation survival, derive the half-diameter absolute-loss bound (known general result), seek nontrivial graph-specific conditions or tighter bounds. Establish prior-art differentiation from statistical partial identification, probabilistic assume-guarantee contracts, QoS composition and goal-oriented experimental design. Stop this direction if no specific result emerges.

G3 PILOT: on frozen P4 and G_SEQPAR, evaluate Jacobian sensitivities of exact or carefully estimated I2 statistics, find local unobservable directions and graph sensitivities, and distinguish sampling noise from structural ambiguity. No parameter-oracle access during method fitting and no new optimizer search.

G4 AUGMENT: if ambiguity affects graph survival, seek a witnessing pair of nearly observationally equivalent providers with separated survival and evaluate predeclared low-cost provider-local additional statistics. Distinguish computational witnesses from certified bounds and prove minimality only within an exhaustively examined disclosure menu.

G5 DECIDE: continue if there is novel survival-specific theory plus validated practical consequences; return to M-focused inference if I2 is effectively sufficient; stop if only generic known bounds are recovered.

## Research integrity
Maintain strict information/method (I/M) separation and the existing PPG firewall. Do not use hidden provider parameters, hidden trajectories, or white-box graph outcomes to select public-interface estimates. Treat all P4/G_SEQPAR findings as development evidence. Preserve source runs and experiments before any new work.

## Prior-art checkpoints
Review full texts and follow-up literature for Manski partial identification, Blackwell/Torgersen comparison of experiments, Allman-Matias-Rhodes latent identifiability, Raue et al. practical identifiability, Kwiatkowska et al. probabilistic assume-guarantee, probabilistic contracts, probabilistic QoS profiles, goal-oriented Bayesian experimental design, and 2026 uncertain probabilistic automata composition (arXiv:2603.29550). Novelty not asserted until checked.
