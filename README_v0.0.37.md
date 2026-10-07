# Stellaris Historian v0.0.37
## The Living Chronicle

This patch deliberately expands **As the Scribes Saw It** before the next combat-correlation stage.

### What changed
- The Scribes Chronicle is much fuller: leaders/commanders, naval development, years of combat activity, science, archaeology and technological advances are woven into the historical narrative.
- Added Technology evidence collection and `Technology_Evidence_Debug.txt`.
- Technology gains are dated conservatively to the first archived state that proves they were known.
- Opening technologies are treated as inherited knowledge, not discoveries on day one.
- Scribes language is now strictly in-universe. It never says “Stellaris preserved...”, “the save says...”, or similar.
- Added `by PillBoxUK` beneath the ASCII launcher title.

### Important evidence rule
A combat activity date proves that a vessel or starbase fought on that date. It does **not** by itself prove the opponent, outcome or casualties. v0.0.37 adds those facts to the Chronicle cautiously; combat correlation remains a later stage.

### Install
Stop Historian, extract this patch over `G:\codex\StellarisHistorian\`, then run `start.bat`. Run **Review Campaign** once to extend all snapshot caches with the new Technology component.

**Restart required: YES.**
