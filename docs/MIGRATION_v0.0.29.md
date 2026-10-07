# v0.0.29 Science Evidence Cleanup & Interpretation

This release does not change the science cache contract. Existing v0.0.28
`science` component version 1 data remains valid and should be read as cache hits.

## What changes

- Adds `historian/domains/science/history.py` for conservative semantic grouping.
- Keeps raw special-project IDs, but groups projects that share the same project
  key into semantic project families.
- Records peak concurrent project instances so multi-target chains are not
  mistaken for accidental duplicates.
- Keeps every Situation ID as a separate episode even when titles/types repeat.
- Re-labels archaeology `completed` dates as chapter/progress markers rather
  than whole-site completion dates.
- Adds lifecycle wording that treats disappearance only as "no longer observed";
  it does not infer completion, failure, cancellation or expiry.
- Review Campaign and Construct Campaign now also write
  `Science_Interpretation_Debug.txt` beside the raw evidence diagnostic.

## Safety

No database schema changes are made. No archived `.sav` files, campaign rows,
processed flags or parsed snapshot caches are deleted or reset.
