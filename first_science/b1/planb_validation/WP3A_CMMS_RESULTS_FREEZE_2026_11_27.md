# WP3a — CMMS external benchmark results freeze

Date: 27 November 2026.
Status: **FROZEN / COMPLETE**, explicitly approved by user. WP1, WP2 and WP5a remain frozen. No manuscript changes. Proceed to WP3b protocol design, not execution.

## Frozen evidence and provenance

- Dataset audit: WP3A1_CMMS_DATASET_AUDIT_2026_11_27.md (570fac6).
- Experimental protocol: WP3A_CMMS_EXPERIMENTAL_PROTOCOL_2026_11_27_V1.md (4352b3a).
- Execution: WP3A_CMMS_IMPLEMENTATION_AND_EXECUTION_2026_11_27.md; executed source commit de0df35730e56360c7bc0b9d19e9731ef2354aa4.
- User local output: ~/praise/wp3a_cmms_2026_11_27_v1.
- Complete evidence ZIP: wp3a_cmms_complete_results_v1.zip, SHA-256 a308a2a59c75b40ec01d55ff1ec6fe74c4f2d83536b1b6ab9bb7733c8df10658.
- Source ZIP SHA-256 f146fff83bba95cc970faf96cc65ea3943f6508f48351d4a9389120e4aaaa4c2; canonical input CSV SHA-256 e6c2a7bb5231c267f1974cefde6bb745bf5bf7f98ba1df7eb612707d92c57038.
- Reference primary.csv SHA-256 882c7d512a957b1ddb40dec4d4fc6d9b429407a94aa2bb0158b7c3003104ea7e; balanced.csv SHA-256 bef5427b106b6abb9026667286922f0c7264056cfaac3a94e63cfac274b38fb9.
- analysis/manifest.json SHA-256 35e2d8b95d68d6aa502d55aaea099eaf2acfe2fda4f9b03607d2cadbf70521e4. It enumerates all case manifests and analysis table digests.
- The complete ZIP is retained by the user; this commit records the freeze and exact evidence identifiers, not a copy of the large ZIP.

Freeze-time recheck: all 18 case manifest hashes and their declared output hashes, additive identity marker, analysis/reference/base_review output hashes verified against archive. Original baseline ZIP files all byte-identical to corresponding complete ZIP files. Total declared counts reconcile: 733,200 scored terminals, 272,400 trajectories, 18,903,600 recorded actions (excludes 800 additive covariance identity replays and synthetic tests). These are retrospective replay records, not additional hardware experiments. User execution logs report all stages PASS; all eight unit tests passed before acquisition, including legacy nine-policy regression. Maximum reported finite mean error 4.163336342344337e-15, no terminal argmin near-ties; baseline coefficient/covariance max error 1.1657341758564144e-15; 800 additive KG paths reproduced. No independent complete rerun at freeze.

## RQ1 and RQ3: primary baseline

376 eligible episodes, 120 method-condition means, 20 equal-weight conditions, 13 relative-coverage budget checkpoints, 20 starts x 20 repeats. Loss = 1 - mean per-episode Raw SLO; no metric or prior changes. Realized reference winner AIF-Hier, mean loss approximately .170937 (Heuristic .178665). Primary endpoint is thirteen-budget mean regret conditional on this reference.

| Policy | Mean regret | Mean PCS |
|---|---:|---:|
| Random | .008114 | .626154 |
| Balanced | .005386 | .700192 |
| Informed | .004547 | .740577 |
| Joint KG | .002168 | .855385 |
| Adaptive two-stage KG | .002417 | .852308 |
| Uniform two-stage KG | .003762 | .809423 |
| Joint Top2 | .002973 | .798846 |
| Adaptive Top2 | .002689 | .799615 |
| Uniform Top2 | .004387 | .745769 |

Adaptive minus comparator aggregate differences and Bonferroni simultaneous 95% familywise intervals (units 0.001 loss; rounded):

| Opponent | Difference | Adjusted interval |
|---|---:|---|
| Random | -5.697 | [-6.664,-4.729] |
| Balanced | -2.968 | [-3.577,-2.360] |
| Informed | -2.130 | [-2.663,-1.597] |
| Joint KG | +.249 | [-.162,+.660] |
| Uniform KG | -1.345 | [-1.940,-.750] |
| Joint Top2 | -.556 | [-.954,-.158] |
| Adaptive Top2 | -.272 | [-.663,+.120] |
| Uniform Top2 | -1.969 | [-2.435,-1.503] |

Six of eight contrasts favor adaptive KG with adjusted intervals excluding zero. Joint KG has lowest observed base regret and highest PCS; adaptive vs joint and adaptive Top2 inconclusive, not established equivalence or universal superiority. Adaptive vs uniform establishes conditional whole-policy benefit of informative condition choice. RQ1 supported in two applications; RQ3 benefit relative to uniform, not general superiority over joint.

## RQ2: structural covariance controls

| Model | Joint KG regret | Adaptive KG regret |
|---|---:|---:|
| Independent | .006150 | .007870 |
| Exchangeable | .005445 | .005154 |
| Additive (primary) | .002168 | .002417 |
| 25% interaction | .001970 | .001945 |

Prespecified primary structural contrast additive minus moment-matched exchangeable: joint -0.003276, nominal matched-stream 95% bootstrap [-.003783,-.002764]; adaptive -0.002736 [-.003196,-.002273]. About 60.2% and 53.1% lower regret. Exchangeable matches marginal variance and mean off-diagonal/latent domain mean variance, so supports factor-specific sharing beyond generic correlation on this catalogue. Additive minus independent joint -0.003981 [-.004434,-.003508], adaptive -0.005453 [-.006083,-.004818]. Interaction25 minus additive joint -0.000198 [-.000403,+.000011], adaptive -0.000473 [-.000707,-.000246]. Secondary nominal evidence for adaptive improvement; joint inconclusive. The 25% component reallocates variance to independent cell-specific effects; not an empirically estimated interaction fraction or proof of a universal optimum. Keep original additive as primary. Do not select better model post hoc. Structural intervals nominal, not multiplicity adjusted.

## Prior and replication robustness

All 14 frozen prior settings evaluated under nine policies. Adaptive mean regret wins vs random, balanced, informed, uniform KG, joint Top2 and uniform Top2 14/14; adaptive Top2 and best observed Top2 13/14; joint KG 6/14 (8 losses), all 14 nominal analytical adaptive-vs-joint intervals include zero. Adaptive rank first/second/third in 6/7/1 configurations. Adaptive minus uniform range [-.002207,-.001143], nominal aggregate analytical intervals exclude zero for all 14. Budget-prior adaptive-vs-uniform 117 wins, 65 ties, 0 losses (first eight checkpoints 14/14, B79 5 wins/9 ties, B93 onward all ties); descriptive finite grid not universal prior insensitivity or simultaneous inference across settings. Balanced 360-run reference retains full nine-policy rank ordering, joint .002122, adaptive .002410, uniform .003790, adaptive-uniform -0.001380 nominal analytical interval [-.001808,-.000953]. Unequal replication does not explain these observed results; not a substitute for reference uncertainty.

## Practical significance (descriptive; defer formal integration to WP5b)

At the illustrative mean regret <= .002 sustained at all subsequent evaluated checkpoints: joint and adaptive KG B43; joint/adaptive Top2 and uniform KG B50; uniform Top2 B57; informed and balanced B79; random B100. Adaptive count savings 57% vs random, 45.6% vs balanced, 14% vs uniform KG. These are first evaluated checkpoints, not interpolated budgets, matched trajectory effort, time savings or guaranteed thresholds. Raw SLO loss and PRAISE MAE differ; common numerical threshold illustrative, no pooled effect sizes.

## Scientific and procedural closure

External physical testbed retrospective benchmark, not blinded prospective replication or independent research group. Fixed archived target, not expected performance in future deployments. Conditional intervals concern policy randomization; source episode dependencies and uncertainty, reference winner robustness, cost heterogeneity and practical significance remain WP5b topics. Raw SLO excludes skipped work and warmup; skip constraint passed all observed runs, not a guarantee of service to all requests. DQN is a controller family with condition-dependent training. No changes to the protocol, no further CMMS experiments required for WP3a. Any future evidence-driven correction or extension must be separately versioned and explicitly justified.

Manuscript integration deferred to WP6. Retain the baseline and all unfavorable findings. Add a CMMS subsection to existing prior sensitivity appendix later. The RQ2 evidence strengthens the structural contribution; WP3b should investigate when factor-informed sharing, interaction residuals and adaptive condition choice help or fail in controlled synthetic regimes, including adverse regimes. Freeze its own design before execution. WP4 competitive baselines and WP5b reference uncertainty/practical significance remain open.
