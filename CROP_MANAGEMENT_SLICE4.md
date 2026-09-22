# Slice 4 — Production Lifecycle + Reconciliation

## A–B. Architecture decision

`farm_crops` already owns one cultivation period, one optional generated plan,
its actual work/inputs, costs, harvests and sales. Its `season` text alone cannot
represent a continuing orchard with separately reconciled future seasons.

Keep `farm_crops` as the execution/production-period record. Add a small parent,
`perennial_plantings`, to preserve the continuing planting identity. A planting
references its original crop record, and that original period plus future
`farm_crops` periods link back to the planting. No new `production_cycles` or
`crop_seasons` execution table is needed. This avoids adding season foreign keys
throughout activities, inputs, expenses, harvests, sales and plans, or trying to
divide their historical data using guessed date ranges.

- Seasonal crops: existing active `farm_crops` → Complete Crop → existing
  `harvested` status, appearing under History.
- Repeated-harvest vegetables: the same cultivation instance accepts repeated
  harvests until Complete Production Period. Repeated harvests alone do not
  require another entity.
- Perennials: the farmer explicitly enables seasons on an established perennial
  crop. That record becomes its first season. Close Season closes that period,
  while the planting remains available for another season.

No automatic interpretation, regrouping or migration of existing crop records.
An existing closed perennial with a known planting date can also explicitly
enable seasons, preserving its existing closed status and records. Enabling
requires crop master `lifecycle_type='perennial'`, an actual planting date and
active/harvested status; crop names are never used to guess perennial behavior.

## C–D. Migration and schema

Revision **`b6e105f1d374`**, following `a5d094e0c263`, applied to guarded local
test and development databases.

New `perennial_plantings` table:

- `perennial_planting_id` identity primary key.
- `source_farm_crop_id` unique restrictive FK to the original cultivation record.
- Required `created_at` and `created_by` audit fields.

Nullable additions to `farm_crops`:

- `perennial_planting_id` restrictive FK.
- `period_started_on` (separate from actual planting).
- `period_request_key`, `period_request_payload` for next-season retries.
- `completed_at`, `completed_by`, `completion_note` for new explicit completions.

No stored aggregate money/quantity fields. Existing historical rows retain NULL
for all new fields. Calling completion again on a legacy harvested record does
not invent an actor or completion timestamp.

Constraints/indexes protect one open season per planting, unique normalized
season names, unique actor/request keys, planting/season identity, audit pairing,
completion status and source foreign keys. A continuing planting's physical
context, actual planting date and planting snapshot cannot be reassigned by
editing a season. Completion audit is immutable once recorded. Empty downgrade
is supported; populated planting/completion history prevents downgrade.

## E–F. Backend changes and APIs

Files:

- `backend/production_lifecycle.py`: new Core SQL router and live reconciliation.
- `backend/crop_management.py`: existing unfinished-task cancellation SQL moved
  into one shared helper, reused unchanged by the old status API and completion.
- `backend/harvest_management.py`: existing summary query moved into a shared
  helper; Slice 3 response contract remains unchanged.
- `backend/main.py`: additive router registration only.
- `backend/alembic/versions/b6e105f1d374_production_lifecycle.py`.
- `backend/tests/test_production_lifecycle.py`.
- `backend/tests/test_production_concurrency.py`.

| Method | API | Access / behavior |
| --- | --- | --- |
| GET | `/my/crop-cycles/{id}/reconciliation` | Farmer capability plus ownership; live current or historical totals |
| POST | `/my/crop-cycles/{id}/complete` | Owning farmer; optional `note`; atomic completion |
| GET | `/admin/crop-cycles/{id}/reconciliation` | Explicit admin capability |
| POST | `/admin/crop-cycles/{id}/complete` | Explicit admin capability; actual admin recorded as actor |
| POST | `/my/crop-cycles/{id}/enable-seasons` | Owning farmer; `season`, `period_started_on`; 201 or 200 on identical retry |
| GET | `/my/perennial-plantings` | Owned plantings, paginated `limit`/`offset` |
| GET | `/my/perennial-plantings/{id}` | Owned planting and its ordered season list |
| POST | `/my/perennial-plantings/{id}/seasons` | Owning farmer; `season`, `period_started_on`, UUID `request_key`, optional `expected_harvest_on` |

All new request models reject extra context fields. Foreign farmer IDs return
404, missing authentication 401, and missing capability 403. Provider-only and
officer-only accounts cannot complete crops or read their reconciliation.
Old crop lifecycle, ledger and Slice 3 APIs remain available.

Completion locks the crop row, records its harvested state/audit and cancels
pending/in-progress/partial tasks in the same transaction. Existing terminal
task records are retained unchanged, and closure notes append to existing notes.
Concurrent completion returns the same original completion audit. Later retries
never overwrite the original note/actor/time. Planned or cancelled crops cannot
be completed by this action. Legacy status API semantics remain unchanged.

New-season creation locks the planting and uses the original request payload plus
actor/request-key uniqueness. Identical retries return the same period, including
after it was closed; changed payloads conflict. Two distinct concurrent starts
cannot create two open seasons. A new start date must follow the previous
season's start date; this slice does not introduce date-window allocation.

## G–H. Farmer UI

Files: `frontend/src/ProductionLifecycle.jsx` and
`frontend/src/CropManagement.jsx`. Existing Slice 3 forms, CSS and the latest
small UI correction remain untouched. Documentation: this report and README.

The same five tabs remain: Overview, Crop Plan, Activities, Expenses, Harvests.
Overview now offers Complete Crop / Complete Production Period / Close Season,
depending on context. Clicking loads live reconciliation. The farmer sees
remaining produce, revenue, expenses and net return before Confirm Completion.
Keep Open cancels the confirmation. Historical crops offer View reconciliation.

The old Harvested dropdown option is replaced by this reviewed completion action
in the farmer UI. Activate and Cancel retain the existing status flow. A completed
period naturally appears in the existing History filter; persisted status remains
`harvested` for compatibility.

Established perennials offer Enable Seasons, then a season history list and Start
Next Season when there is no open season. My Crops → Current also shows persistent
perennial plantings, including when every previous season is closed. Opening one
shows its source period and season navigation. The next season opens in the same
crop workspace. No repeated farm, plot, block or crop selectors are added.

## I. Reconciliation

Reuses `harvest_events`, `harvest_sales` and crop-linked `farm_expenses`.

For each unit separately:

`harvested = sold + wastage + remaining`

`net_return = total_revenue - total_expenses`

Response includes quantity groups, revenue, expenses, net return, INR currency,
cycle state and available completion audit. No mixing kg/crates/bags and no
assumed conversions. Unsold produce never blocks completion. Zero-harvest crops
and negative net return remain valid. Farm-wide overhead is not allocated.

Historical harvest/sale/expense corrections and late entries continue under
existing authorization. Reconciliation reads current saved facts, so historical
totals reflect those corrections while original completion audit stays fixed.
The confirmation is a live preview, not a frozen financial statement: concurrent
or subsequent authorized corrections may change displayed totals.

## J. Perennial seasons

Closing mango Season 2026–27 changes only that `farm_crops` period. Its planting
remains accessible, and Season 2027–28 receives a new `farm_crops` ID with the
same farm/plot/block/crop and original planting identity/snapshot. No old plan,
tasks, work, inputs, expenses or harvests are copied into the next season.
All existing record APIs therefore remain naturally scoped to one period.

Actual `planted_on` is inherited unchanged; a new season is not a new planting.
`period_started_on` is explicit, never silently today's date. New seasons start
active; recording a harvest still never activates, closes or completes anything.

Existing SOP scheduling remains planting-based, including its anchor-date
validation. This slice does not reinterpret days-after-planting SOP tasks as
days-after-season-start. Seasonal SOP scheduling is not introduced; manual
activities remain available for recurring-season work. Tree-level identity,
orchard retirement and combining pre-existing independent crop records are also
outside this additive slice.

## K–N. Tests and validation

- **280 backend tests passed**: all **254 baseline** tests plus **26 new** cases.
- New coverage: seasonal/vegetable completion, repeated harvests, unsold amounts,
  unit-separated quantities, revenue/cost/net totals, history filtering, live
  historical corrections, task closure/work/input preservation, authentication,
  ownership/admin/officer access, legacy audit preservation, next-season context
  and record isolation, duplicate/invalid seasons, SQL identity guards, injected
  transaction rollback, real completion/sale/retry races, migration preservation
  and guarded downgrade.
- Command from `backend`: `..\.venv\Scripts\python.exe -m pytest tests -q`.
- Two unchanged backend dependency deprecations: Starlette/httpx TestClient and
  AnyIO BlockingPortal alias.
- Frontend `npm.cmd run build`: **passed**, 52 modules.
- Frontend `npm.cmd run lint`: **passed**, zero errors; the same 14 existing
  warnings, none added by these changes.
- React server-render checks passed for completion action labels, perennial
  enable-seasons entry, remaining/net display and workspace imports.
- Existing marketplace/auth/onboarding and Slice 1–3 tests remain green. No old
  tests or migrations were modified. No new dependencies or ORM introduced.

## O. Existing data verification

All **44 pre-existing development tables** retained identical row counts and
original-column data fingerprints across the migration. The new planting table
was empty, and all seven new fields on existing `farm_crops` rows remained NULL.
Both guarded databases were verified at `b6e105f1d374`. Disposable concurrency-test
schemas were cleaned up.

## P. Manual browser/mobile checks still required

No browser was available in this session. Server rendering/build/lint do not prove
interactive behavior or mobile layout. Restart the backend, then perform:

1. Sign in as a farmer. Open a fresh active seasonal crop. Record 1,000 kg harvested,
   50 kg wastage, a sale of 900 kg for ₹45,000, and crop expenses ₹28,000.
2. Confirm recording harvests leaves the crop active. In Overview choose Complete
   Crop. Verify harvested 1,000 kg, sold 900 kg, wastage 50 kg, remaining 50 kg,
   revenue ₹45,000, expenses ₹28,000 and net ₹17,000.
3. Choose Keep Open; verify no state change. Review again and Confirm Completion.
   Confirm it appears under History with all records retained and unfinished plan
   tasks cancelled with a note; completed/not-applicable/already-cancelled tasks
   must stay unchanged.
4. Reload or retry confirmation; verify the completion audit does not change.
   In History correct a sale/harvest/expense; reopen reconciliation and check live
   totals update. Record a late sale against the original harvest, not a new season.
5. Repeat with a vegetable crop and multiple harvests. Verify Complete Production
   Period, mixed units remaining separate, and unsold produce allowed.
6. Use an established crop whose catalogue lifecycle is Perennial, with actual
   planting date populated. Open Overview → Enable Seasons. Enter the existing
   season name and its explicit start date. Confirm original records remain.
7. Record several harvests/sales. Review Close Season and confirm. Return to My
   Crops → Current: the perennial planting must remain visible. Its closed season
   must also be available in History and the planting's season list.
8. Choose View Seasons / Start Next Season. Enter a distinct next-season name and
   later start date. Confirm same farm/plot/block/crop, original actual planting
   date, separate season start, active status and empty new work/cost/harvest totals.
9. Add harvests and expenses in the new season. Verify prior season reconciliation
   is unchanged. Attempt another open season or duplicate season name: reject.
10. Check another farmer/provider cannot access/complete these crops. An admin may
    use documented `/admin` completion/reconciliation routes with its own actor.
11. At 360px, 390px and desktop widths check all five tabs, confirmation, errors,
    season forms/history, long names and touch targets; ensure no horizontal
    overflow. Check slow/retried saves and next-season navigation.
12. Smoke-test existing sign-in/onboarding, farms/plots/blocks, planting edits on
    non-season crops, marketplace bookings, provider availability, payments,
    reviews, and Slice 3 harvest/sale corrections.

Stopped at Slice 4. No Task-to-Booking, produce marketplace, delivery, subscriptions,
logistics, agronomist workspace, livestock, leases, tree tracking, inventory,
weather, AI or advanced expense allocation was added.


## Slice 6 scheduling update

See [CROP_MANAGEMENT_SLICE6.md](CROP_MANAGEMENT_SLICE6.md) for season-start planning, automatic season labels and classified stage/condition/manual tasks. The earlier slice behavior above describes its historical baseline; existing saved plans remain unchanged.
