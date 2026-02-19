# FieldMonitoring25m

Hybrid agriculture monitoring platform focused on polygon AOIs, native Sentinel-2 analytics, and SR close-up exploration.

## What is implemented
- Polygon lifecycle: draw and upload (`GeoJSON`, `KML`, `ZIP Shapefile`) with area limit enforcement (`<= 10,000 ha`).
- Farm/field hierarchy with org RBAC (`OWNER`, `ADMIN`, `ANALYST`, `VIEWER`).
- Planetary Computer integration for Sentinel-2 scene search.
- Native index analytics pipeline (`NDVI`, `NDMI`, `NDWI`, `EVI`, `NDRE`, `SAVI`).
- Quality gate policy: cloud cap + valid-pixel threshold with `LOW_QUALITY_SKIPPED` status.
- Real SR4RS inference flow via `sr.py` (OTBTF-based container worker) and model-derived labeling.
- Optional S2DR3 external provider mode (HTTP endpoint or external command template).
- Daily monitoring scheduler (Celery beat), in-app alerts, and export jobs (`GeoTIFF`, `CSV`, `PNG`).
- Responsive Next.js app with draw tools, index switcher, map mode switcher, timeline, alert center, and export actions.
- Dev stack for Apple Silicon and prod profile for Linux GPU workers.

## Repository layout
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/apps/web`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/apps/api`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/apps/worker`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/apps/tiler`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/packages/shared-types`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/infra/docker`
- `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/infra/migrations`

## Quick start (M1 dev)
1. Copy env file:
```bash
cp .env.example .env
```
2. Start services:
```bash
docker compose --profile dev up --build
```
3. Open app:
- Web: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8002/docs](http://localhost:8002/docs)
- Tiler: [http://localhost:8081](http://localhost:8081)
- MinIO Console: [http://localhost:9001](http://localhost:9001)

## Prod profile (Linux GPU)
```bash
docker compose --profile prod --profile gpu up -d --build
```
`worker-gpu` consumes `sr_gpu` queue and requires NVIDIA container runtime.

## SR providers
### SR4RS (real inference, recommended on Linux GPU)
- Set in `.env`:
```bash
SR_PROVIDER=sr4rs
SR4RS_SCRIPT_PATH=/opt/sr4rs/code/sr.py
SR4RS_MODEL_DIR=/workspace/.cache/sr4rs/sr4rs_sentinel2_bands4328_france2020_savedmodel
SR4RS_MODEL_URL=https://nextcloud.inrae.fr/s/boabW9yCjdpLPGX/download/sr4rs_sentinel2_bands4328_france2020_savedmodel.zip
```
- SR jobs route to `sr_gpu` automatically when `include_sr=true` and `SR_PROVIDER=sr4rs`.
- Model files are cached under `/Users/mohamedboujaha/2025projects/fieldmonitoring25m/storage/sr4rs-cache`.

### S2DR3 external mode (optional)
- Set:
```bash
SR_PROVIDER=s2dr3_external
```
- Pick one integration:
```bash
S2DR3_EXTERNAL_ENDPOINT=https://your-s2dr3-service/infer
```
or
```bash
S2DR3_COMMAND_TEMPLATE=python /opt/s2dr3/infer.py --date {date} --geojson {geojson} --output {output}
```
- Command placeholders supported: `{date}`, `{geojson}`, `{output}`, `{bbox_w}`, `{bbox_s}`, `{bbox_e}`, `{bbox_n}`.

## Key queues
- `analysis_cpu`
- `sr_gpu`
- `exports`

## API coverage
Implemented under `/api/v1`:
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /orgs`
- `POST /orgs/{org_id}/invites`
- `GET /orgs/{org_id}/feature-flags`
- `PUT /orgs/{org_id}/feature-flags/{key}`
- `POST /farms`
- `GET /farms`
- `POST /fields`
- `POST /fields/import`
- `PATCH /fields/{field_id}`
- `GET /fields/{field_id}/imagery/search`
- `POST /fields/{field_id}/analyses`
- `GET /fields/{field_id}/timeseries`
- `GET /layers/{layer_id}/metadata`
- `GET /tiles/{layer_id}/{z}/{x}/{y}.png`
- `POST /exports`
- `GET /exports/{export_id}`
- `GET /alerts`
- `POST /alerts/{alert_id}/ack`

## Hybrid logic implemented
- Native indices are the default analytic source.
- SR outputs are model-derived and labeled.
- SR analytics require feature flag `sr_analytics_enabled`.
- Band compatibility enforced for index availability.
- SR provider is configurable per deployment (`sr4rs`, `s2dr3_external`, or `nearest` debug fallback).

## Notes
- SR4RS worker image clones `https://github.com/remicres/sr4rs` at build time and runs `sr.py`.
- Tile endpoint currently serves model-aware placeholder tiles; integrate direct TiTiler source URLs in the next hardening pass.
