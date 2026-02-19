# Acceptance checklist (manual)

1. Register and login via `/api/v1/auth/register` and `/api/v1/auth/login`.
2. Create organization and farm.
3. Draw polygon in web map and save field.
4. Search imagery and queue analysis.
5. Verify time series appears with native index stats.
6. Enable SR analytics feature flag and rerun with SR toggle.
7. Verify SR values appear only for compatible indices and are model-labeled.
8. Trigger export jobs for CSV, PNG, GeoTIFF and verify output URI.
9. Review alerts and acknowledge one.
10. Confirm daily scheduler enqueues analysis jobs.
