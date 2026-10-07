# Migration v0.0.48.1

v0.0.48 used a generic journal-refresh anchor while patching Review Campaign. That anchor matched the earlier Update History route, unintentionally deleting the `/api/live-history` and `/api/review-campaign` route definitions.

v0.0.48.1 rebuilds `app.py` from the automatic `backups/v0.0.48/app.py` copy, reapplies only the intended v0.0.48 app changes using route-scoped anchors, validates the four campaign POST routes, and compiles `app.py` before marking the hotfix complete.

No database or archived-save changes are made.
