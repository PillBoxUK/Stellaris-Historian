# Stellaris Historian v0.0.36
## Empire Timeline + Scribes Authorship + Direct PDF Export

This patch is intentionally presentation-focused before the next combat-correlation stage.

### New
- **Empire Timeline**: simple year-by-year events with category filters and `People of Note` callouts.
- **As the Scribes Saw It** remains permanently and now includes evidence-led ruler-authored sign-off blocks.
- The **final Chronicle page remains unsigned** because the active campaign is still being written.
- **Export PDF** on Scribes creates a real `Scribes_Chronicle.pdf` directly; browser print remains available separately.
- Historical Journal now links directly to **Empire Timeline** as well as **As the Scribes Saw It**.

### Evidence rules
- Signatories come from actual dated ruler observations in the cached leader evidence.
- `last_combat_activity` can only appear as cautious combat activity until stronger correlation exists.
- No unsupported battle result, casualty, death, speech, motive or succession reason is invented.

### Install
1. Stop Stellaris Historian.
2. Extract this ZIP over `G:\codex\StellarisHistorian\` and allow overwrite.
3. Run `start.bat`.
4. The launcher will install the added ReportLab dependency automatically if required.
5. Open **View Journal**. You can now choose **Empire Timeline** or **As the Scribes Saw It**.
6. In Scribes View, use **Export PDF** for the book-style PDF.

**Restart required: YES.**

GitHub repository initialized.
