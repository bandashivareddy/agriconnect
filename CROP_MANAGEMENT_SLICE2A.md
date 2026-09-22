# Crop Management Slice 2A: field work

## A. Existing structures reused

Existing JWT authentication, users, multi-capability checks, farmer ownership,
farms/plots, `farm_crops` cultivation instances, generated `crop_tasks`, India
business dates/derived overdue behavior, guarded Alembic migration helper, and
mobile Crop Management styling/API helper. No separate officer login or profile
is needed. Legacy `user_role` values remain unchanged.

## B. Files changed

Added:
- `backend/field_work.py`
- `backend/alembic/versions/d2a041f9b620_field_work.py`
- `backend/tests/test_field_work.py`
- `backend/tests/test_field_work_concurrency.py`
- `frontend/src/FieldWork.jsx`
- `frontend/src/FieldWorkAdmin.jsx`
- `CROP_MANAGEMENT_SLICE2A.md`

Updated:
- `backend/main.py`: include the isolated field-work router.
- `frontend/src/App.jsx`: capability-aware navigation and field-work entry points.
- `frontend/src/AdminDashboard.jsx`: Manage Field Work entry.
- `frontend/src/CropManagement.jsx`: read-only farmer field-work section.
- `README.md`: module documentation link.

## C. Migration

Revision `d2a041f9b620`, following `c901a7b2d310`, applied first to the guarded
local test database and then to the guarded local development database.
No baseline SQL rewrite or historical data backfill. Downgrade refuses to discard
populated field-work history or assigned officer capabilities.

From repository root, for another appropriately configured local environment:

```powershell
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target test
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target development
```

## D. Schema and capability

Four new tables:
- `crop_officer_assignments`: officer/cycle, assigning actor, status, notes, audit timestamps.
- `field_visits`: assignment, planned date, start/completion, status, notes, audit actors/timestamps.
- `visit_tasks`: visit/task composite key, verification outcome/note/time/actor.
- `field_observations`: visit, controlled type/severity, factual title/notes, observed time and audit fields.

`user_capabilities` now permits `field_officer`; existing capabilities are retained.
Visit cycle/officer ownership is derived from its immutable assignment, and
observation ownership from its visit. This avoids inconsistent duplicated IDs;
API responses include the resolved cycle/officer identifiers.

Partial unique index prevents duplicate active officer/cycle assignments. Other
indexes support cycle history, visit scheduling, task reverse lookup, and recent
observations. Foreign keys restrict history deletion; checks constrain statuses,
verification metadata and lifecycle timestamps. A trigger rejects cross-cycle
visit/task links; another protects assignment identity.

## E. APIs

| Method | Route | Purpose |
|---|---|---|
| GET | `/admin/field-work/users?q=` | Search existing accounts |
| GET / POST | `/admin/field-officers` | List officers / grant capability to existing account |
| GET | `/admin/field-work/crop-cycles` | Search crop cycles for assignment |
| GET / POST | `/admin/field-work/assignments` | List / create assignments |
| PATCH | `/admin/field-work/assignments/{id}` | Edit notes or close assignment |
| GET / POST | `/admin/field-work/visits` | List / schedule visits |
| GET | `/admin/field-work/visits/{id}` | Read visit detail |
| POST | `/admin/field-work/visits/{id}/cancel` | Cancel unfinished visit with reason |
| GET | `/field-work` | Officer's active assignments and visits |
| GET | `/field-work/crop-cycles/{id}` | Assigned crop summary |
| GET | `/field-work/visits/{id}` | Assigned visit, tasks and observations |
| POST | `/field-work/visits/{id}/status` | Start / complete visit |
| PUT | `/field-work/visits/{id}/tasks/{task_id}` | Record verification |
| POST | `/field-work/visits/{id}/observations` | Create factual observation |
| PUT | `/field-work/visits/{id}/observations/{observation_id}` | Edit own observation |
| GET | `/my/crop-cycles/{id}/field-work` | Farmer's read-only history/observations |
| GET | `/my/crop-cycles/{id}/field-visits/{visit_id}` | Farmer's read-only visit detail |

Assignment/visit status mutations require `expected_status`. Verification edits
require matching `expected_updated_at` after initial verification; observation
edits require matching `expected_updated_at`. Stale/conflicting changes return
409. Capability grants and identical verification retries are idempotent.

## F. Authorization and lifecycle

All authorization is server-side. Admin routes require admin capability. Officer
routes require officer capability and the officer's own active assignment;
missing/unassigned records return safe 404, missing capability returns 403.
Farmer routes require farmer capability and crop ownership. Provider capability
alone grants no field-work access. Admin status does not impersonate an officer.

Assignments move from active to completed/cancelled; reopening is not supported.
Closing an assignment atomically cancels its unfinished visits and retains their
notes/evidence. Reassignment creates a new historical record; it does not restore
access to the old assignment's visits.

Officer visit transitions are planned -> in_progress -> completed. Admin may
cancel unfinished visits. Only in-progress visits accept observations or task
verification; completed/cancelled visits are read-only. Completion may retain
unverified tasks. Cancellation appends a reason without erasing existing notes.

Mutations lock assignment then visit consistently. Task verification never
changes Crop Task execution status, generated content, or crop lifecycle.
Observation types are general/crop_condition/pest/disease/weed/water/nutrient/damage;
severity is low/medium/high/critical. Prescriptions are not a supported payload
or workflow; free-text fields are explicitly presented as factual observations.

## G. Frontend

- Officer: My Field Work, today/upcoming visits, assigned crop cards, visit detail,
  start/complete, task verification and factual observation creation/editing.
- Farmer: Crop Cycle detail shows assigned officers, latest visit, history and
  recent observations; visit details are read-only.
- Admin: Manage Field Work, existing-account capability grant, assignments,
  scheduling, history and cancellation.

Uses existing responsive cards, form controls and Crop Management CSS. Officer
work is reachable without unrelated farmer/provider onboarding; those existing
workflows still retain their own onboarding gate. After capability grant, sign
out and sign in to refresh frontend navigation.

## H–K. Validation and regression results

Final backend run: **130 passed**, including **25 new field-work tests**, all
**68 Slice 1 tests**, and all **37 original regression tests**. Coverage includes
capability compatibility, duplicate assignments/history, cross-user access,
visit lifecycle, validation, farmer read-only access, unchanged execution status,
stale edits, preserved cancellation notes, rollback atomicity, concurrent writes,
cross-cycle DB protection, and migration/downgrade compatibility.

Two existing backend dependency deprecations remain: Starlette/httpx TestClient
and AnyIO BlockingPortal alias. Frontend production build passes. Lint exits zero
with the same **14 existing warnings**, no new warnings/errors. Existing warnings
are React effect/dependency warnings in App, AdminDashboard, BookingForm, FarmSetup,
MyServices, Notifications, SupplierAvailability, SupplierDashboard and SupplierEquipment.

No automated regression failures. Browser-based end-to-end/mobile visual checks
were not performed; the following manual checks remain necessary.

## L. Deferred items

Photo uploads/attachment ownership are deferred. The existing provider upload
validation pattern was reviewed; provider verification documents/storage are not
repurposed. A future visit-specific attachment can reference visit/observation IDs.
No unnecessary officer profile/HR table, agronomist role, prescriptions, irrigation
or fertilizer execution, expenses, harvest accounting, profitability, produce
marketplace, weather/AI, booking integration, routing, payroll, offline sync, or
plot-area sum validation is added.

## M. Manual end-to-end checks

1. Restart the backend/frontend using the normal project startup procedure.
2. Sign in as a farmer. In My Crops, create/select a crop cycle and generate a
   published SOP plan with tasks due today or earlier. Note a task's execution status.
3. Sign in as admin. Open Manage Field Work. Search for an existing officer account,
   select it and enable field officer access. Confirm existing farmer/provider
   access is retained. Select that officer and the crop cycle, then create an assignment.
4. Schedule a visit for today and another for a future date. Confirm duplicate
   active assignment of the same officer/cycle is rejected.
5. Sign out and sign in as the officer. My Field Work should show today's/upcoming
   visits and assigned crops. Open today's visit and start it.
6. Verify a crop task as observed completed; verify another as partial/not done
   with a note. Add a factual observation (e.g. water, medium severity) and edit it.
   Confirm the underlying task execution statuses have not changed.
7. Enter visit notes and complete the visit. Confirm verification/observations are
   now read-only, including if some tasks remain unverified.
8. As the owning farmer, open My Crops -> crop detail. Check assigned officer,
   latest visit, recent observations and read-only visit detail. No officer edit
   controls should appear.
9. As admin, close the assignment. Confirm its unfinished future visit is cancelled
   and completed visit/history remain. The officer must lose access, including
   when requesting the old visit URL through the API.
10. Create a new assignment for the same or another officer; verify history remains
    and the new assignment does not reopen old visits. A second unassigned officer,
    unrelated farmer and provider-only account must not access this crop's field work.
11. At 360px and 390px widths, check cards, controls, observation forms, errors,
    task verification and completion without horizontal scrolling.
12. Smoke-test existing farmer/provider sign-in/onboarding, farms/plots, marketplace
    search, service booking, provider availability, payments/reviews and Slice 1
    SOP publication/plan generation/task updates through their existing screens.


## Slice 7 application workflow

[Slice 7](CROP_MANAGEMENT_SLICE7.md) adds shared signup and reviewed Field Officer applications. Approval grants workspace access only; the assignment rules described above remain unchanged. Pending/rejected applicants must use application review instead of the legacy staff grant shortcut.
