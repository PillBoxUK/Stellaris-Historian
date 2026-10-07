# Migration v0.0.50.2

The v0.0.50.2 hotfix changes only First Contact name interpretation and release metadata.

It does not modify archived `.sav` files, campaign IDs, SQLite history rows, processed flags, or parsed-cache component versions.

The hotfix replaces the First Contact history/journal modules, updates release metadata, and records `data/.migration_v0_0_50_2_complete`. Existing `First_Contact_History.json` is refreshed the next time Update History, Live History, Review Campaign, or Construct Campaign invokes the structured First Contact refresh.
