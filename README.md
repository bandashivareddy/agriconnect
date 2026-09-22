# AgriConnect

## Working baseline

- Python 3.14.7
- PostgreSQL
- React + Vite frontend

## Backend setup (Windows PowerShell)

From the project root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Set the required database and JWT values in `backend\.env`. PostgreSQL must
be running and the configured `DB_NAME` database must already exist.

`LOG_LEVEL` is optional and defaults to `INFO`. Standard Python levels such as
`DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL` are supported; invalid
values safely use `INFO`.

For pilot configuration, `CORS_ORIGINS` and `TRUSTED_HOSTS` accept
comma-separated values. Their local defaults preserve Vite development; add
the relevant LAN address or deployed hostname when needed. Set
`ENABLE_API_DOCS=false` to disable `/docs`, `/redoc`, and `/openapi.json`.

Provider verification uploads are stored locally by default in
`backend/storage/provider_documents`. Configure `DOCUMENT_STORAGE_DIR` and
`MAX_DOCUMENT_UPLOAD_MB` (default `5`) for a pilot environment. Storage is
not publicly served; providers and admins access uploaded documents through
authenticated API routes. Malware/antivirus scanning remains a future
production requirement.

Start the backend:

```powershell
cd backend
uvicorn main:app --reload
```

## Frontend setup

In another PowerShell window, from the project root:

```powershell
cd frontend
npm install
npm run dev
```

## Tests

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest
```

Tests require a dedicated `AGRI_TEST_DB_NAME`. It must be non-empty, differ
from `DB_NAME`, contain `test`, and match PostgreSQL's `current_database()`.
The suite refuses to run if these safeguards are not met.

## Database migrations

Run these commands from `backend` with the virtual environment active:

```powershell
alembic current
alembic history
alembic upgrade head
alembic revision -m "description"
```

The baseline migration was derived from the existing PostgreSQL schema. Do
not run its `upgrade` against an existing AgriConnect database: first verify
its schema matches the baseline, then use `alembic stamp 44d0107abf58`.

AgriConnect uses SQLAlchemy Core and handwritten SQL rather than complete
declarative metadata. Do not treat `alembic revision --autogenerate` as
authoritative. Future schema changes must be written and reviewed explicitly
as Alembic revisions; each new table, column, index, constraint, or nullable
change needs a revision.

The baseline downgrade is intentionally unsupported because it would be
destructive. Test any future downgrade only on a disposable database.

## Database operations

Before a significant pilot migration, create and verify a backup. On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\backup_database.ps1
```

The script reads database settings from process environment variables or
`backend\.env`, writes a timestamped PostgreSQL custom-format dump to
`backend\backups`, and never prints the database password. It requires
`pg_dump` to be installed and available on `PATH`.

Test a restore only in a new disposable database, never the active pilot
database. Use PostgreSQL credentials through a secure prompt or environment,
then run commands like these from PowerShell:

```powershell
createdb --host=<host> --port=<port> --username=<user> agriconnect_restore_check
pg_restore --host=<host> --port=<port> --username=<user> --dbname=agriconnect_restore_check .\backend\backups\<backup.dump>
```

Verify schema/table presence and application health against that new database
before considering any recovery procedure. Do not use `--clean`, `dropdb`, or
an active pilot database as the restore target.

Existing databases use Alembic revision tracking. New schema changes require
explicit reviewed revisions; autogenerate is not authoritative because the
application uses handwritten SQL. Do not make ad-hoc production schema
changes, and retain the dedicated test-database safeguards described above.

## Account onboarding

Sign-in accepts a mobile number or email with the existing password. Registration
requires at least one contact method; email is optional. Phone formatting spaces,
parentheses, hyphens and a leading plus are ignored for lookup.

The frontend resumes setup from saved data on sign-in/reload. Farmers create a
farm and service address using FarmSetup. Providers complete ProviderProfile and
add their first service using MyServices. Becoming a provider reuses the farmer's
account and retains farmer access. Provider setup is complete in the UI only
after a service has been saved; existing API capability checks are retained.

Before running this version against another existing database, apply the optional
email migration from `backend`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
```

This changes only `users.email` nullability; unique email/phone constraints remain.
Existing installations must already be stamped at the baseline revision as
specified in the database setup instructions. Do not run the baseline creation
against an existing unstamped schema.

Onboarding regression coverage is in `backend/tests/test_onboarding.py`. Run the
backend test suite from `backend` against the guarded test database described in
`backend/tests/README.md`.

## Crop Management Slice 1

The additive Crop Management module is documented in
[CROP_MANAGEMENT_SLICE1.md](CROP_MANAGEMENT_SLICE1.md), including APIs, guarded
migration commands, validation results, and manual admin/farmer test steps.
Farmer entry: **My Crops**. Admin entry: **Manage Crop SOPs**.

## Crop Management Slice 2A

Assignment-scoped officer visits, task verification, and factual observations are
documented in [CROP_MANAGEMENT_SLICE2A.md](CROP_MANAGEMENT_SLICE2A.md).
Officer entry: **My Field Work**. Admin entry: **Manage Field Work**.
Farmers can read field-work updates from Crop Cycle detail.

## Crop/Farm Management Slice 2B

Shared actual activities, expenses and optional plot blocks are documented in
[CROP_MANAGEMENT_SLICE2B.md](CROP_MANAGEMENT_SLICE2B.md), including schema/API
decisions, migration status, validation and browser/mobile test steps.
Farmer entry: **My Crops**, then **Activities / Expenses** on a crop or
**Farm Activities & Expenses / Manage Blocks** for farm-wide history.

## Crop/Farm Management Slice 2C

Optional variety/source snapshots, duration estimates, input catalogues and actual
activity inputs are documented in [CROP_MANAGEMENT_SLICE2C.md](CROP_MANAGEMENT_SLICE2C.md).
Admin entry: **Crop & Input Catalogue**. Farmer entry: **My Crops** planting details
and **Activities / Record Work → Add Input**. Existing expenses remain the cost record.

## Slice 2D — My Crops navigation

My Crops now opens on **Current**, with **History** alongside it. Each crop shares
Overview, Crop Plan, Activities and Expenses. Blocks are managed from
**My Farms → Farm → Plot → Blocks**; farm-wide records remain a secondary Farm Details
action. **No migration required for Slice 2D.** See
[CROP_MANAGEMENT_SLICE2D.md](CROP_MANAGEMENT_SLICE2D.md) for validation and manual steps.

## Crop/Farm Management Slice 3

Harvests and sales are available inside My Crops. See [CROP_MANAGEMENT_SLICE3.md](CROP_MANAGEMENT_SLICE3.md) for schema, APIs, validation and manual checks. Existing farm expenses remain the source of crop costs.

## Crop/Farm Management Slice 4

Overview now includes reconciliation and crop/season completion. Continuing perennial plantings reuse crop records for separate seasons. See [CROP_MANAGEMENT_SLICE4.md](CROP_MANAGEMENT_SLICE4.md) for architecture, APIs, validation and manual checks.

## Crop/Farm Management Slice 5

Optional Crop Plan task services reuse existing marketplace bookings, followed by farmer-confirmed work and actual expenses. See [CROP_MANAGEMENT_SLICE5.md](CROP_MANAGEMENT_SLICE5.md) for schema, APIs, validation and manual checks.

Crop Management Slice 6: [season planning implementation and manual tests](CROP_MANAGEMENT_SLICE6.md).

Crop Management Slice 7: [shared signup and Field Officer applications](CROP_MANAGEMENT_SLICE7.md).
