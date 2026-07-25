# Identity Evolution Analysis — Quality Improvement v1.0

## Symptom

Staging Night Growth formal: `identity_update.patches=0`.

## Root causes (not “threshold too high”)

| # | Cause | Evidence |
|---|--------|----------|
| 1 | **No reflection on conversation turns** | NG report `reflection.count=0` when loading V1 rows without reflection field |
| 2 | **`IDENTITY_UPDATE_MODE=candidate`** | Formal version bump intentionally blocked; candidates only |
| 3 | **Identity only from reflection lessons** | Old NG path ignored preference / self-intro signals |
| 4 | **Hollow reflection** | Summary without actionable lessons → no trustworthy patch |

**Not fixed by lowering confidence threshold** (spec forbidden).

## Corrections

1. Reflection quality → more real `lessons` + quality gate  
2. NG `_maybe_identity_update`:
   - Prefer **actionable** reflection lessons with conf ≥ 0.55 (unchanged gate)
   - Else preference / self-intro → `relationship_context` patch (still versioned / candidate-aware)
3. Decision marks `identity_signal` for self_intro / preference tags  
4. Candidate mode still correct for Staging: expect **candidates**, not always formal patches

## Result

| Mode | Expected |
|------|----------|
| candidate | `identity_candidates` increase; formal patches may stay 0 |
| formal + actionable reflection conf≥0.55 | formal version possible |
| chitchat only | no identity write |

Test: `test_identity_candidate_from_preference_without_lowering_threshold`.
