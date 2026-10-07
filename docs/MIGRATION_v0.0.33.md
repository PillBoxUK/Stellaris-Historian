# Migration v0.0.33 - Combat Evidence Foundation

v0.0.33 adds a modular Combat domain and a new parsed-snapshot cache component named `combat` at version 1.

The migration does not delete or rebuild campaign archives, `historian.db`, processed flags, or existing cache containers. Existing cached snapshots remain reusable; on the first Review Campaign, snapshots that do not yet contain the Combat component are extended from the corresponding archived `.sav` file.

Combat is deliberately evidence-first in this release. Historian collects player-related active war records and direct player battle records retained by Stellaris, including exact battle dates, attacker/defender side, recorded victory/defeat, aggregate losses, battle type, and system/planet IDs/names where resolvable.

The migration does not publish combat narrative into the Historical Journal yet. Review/Construct instead writes `Combat_Evidence_Debug.txt` into the campaign archive folder for validation.

Historian does not interpret a missing ship or fleet as destroyed. Exact named-vessel losses will only be added later when disappearance windows can be safely correlated with stronger combat evidence.
