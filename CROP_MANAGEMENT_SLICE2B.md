# Crop/Farm Management Slice 2B — implementation report

## A. Architecture decisions

Track Myself and Use Crop Plan share `farm_activities` and `farm_expenses`.
`crop_tasks` remains planned work; `visit_tasks` remains field verification.
Neither is replaced or implicitly updated by recording an activity. A crop task
can have multiple actual work events. An activity can have multiple expenses;
both activities and expenses can stand alone at farm scope.

The inspected schema had no block/sub-plot entity. Blocks are optional children
of existing plots. A nullable `farm_crops.farm_block_id` places a cultivation in a
block; existing cultivations remain unblocked. No separate crop-group systems,
tree model, or production-season model is introduced.

Booking records have an existing nullable farm reference, so activities support
an optional reference to a booking that explicitly names the same owned farm.
Bookings without a farm are ineligible. The reference does not change booking
status, price, payment or settlement, and creates no automatic expense. Booking
link selection is API-only in this slice.

## B. Existing structures reused

SQLAlchemy Core and parameterized SQL, the shared database engine, JWT auth and
effective capabilities, farmer ownership, Slice 2A active assignments and visits,
farms/plots/crop cycles, generated crop tasks, existing bookings, strict request
models, guarded Alembic tooling, mobile Crop Management CSS and API helper.
No declarative ORM conversion, new authentication system or broad main.py refactor.

## C. Files changed

Added:
- `backend/alembic/versions/e3b072c8a941_farm_ledger.py`
- `backend/farm_ledger.py`
- `backend/tests/test_farm_ledger.py`
- `backend/tests/test_farm_ledger_concurrency.py`
- `frontend/src/FarmLedger.jsx`
- `CROP_MANAGEMENT_SLICE2B.md`

Updated:
- `backend/main.py`: include the new router and tighten legacy harvest-date validation.
- `backend/crop_management.py`: optional block support and managed date validation.
- `frontend/src/CropManagement.jsx`: crop navigation, Record Work, optional block selection and farm workspace entry.
- `frontend/src/FieldWork.jsx`: assigned officer factual activity recording/history.
- `README.md`: link to this report.

Previous migration files, baseline SQL and existing tests were not edited.

## D. Migration

Revision **`e3b072c8a941`**, parent **`d2a041f9b620`**.
Applied first to the guarded test database, then to guarded development after the
complete test/build/lint run passed. Both heads and all three new tables verified.
All pre-existing development table row counts and all pre-existing cultivation
field values were compared before/after and preserved. No temporary test schemas remain.

For another correctly configured local environment, from repository root:

```powershell
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target test
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target development
```

The explicit downgrade refuses to discard populated activity, expense or block
history. No manual SQL is required for normal upgrade.

## E. Tables, columns and constraints

| Structure | Main fields |
|---|---|
| `farm_blocks` | farm/plot, name, description, optional area/unit, active/inactive, audit actors/timestamps |
| `farm_crops.farm_block_id` | nullable FK to a block; existing values remain null |
| `farm_activities` | farm/plot/block/crop context, optional task/visit/booking, type/date/description, optional quantity/unit/performer, source, notes, audit fields, request key/payload |
| `farm_expenses` | same context, optional activity, date/category, exact decimal amount, vendor/person, payment mode, notes, audit fields, request key/payload |

Amounts use PostgreSQL `numeric(14,2)`, must be positive, and are recorded in INR.
There is no currency conversion, payment transaction or full accounting model.
Quantities/areas use `numeric(14,4)`. API validation rejects non-finite values,
excess precision, nonpositive values, and unpaired quantities/units or areas/units.

Foreign keys protect references/history. Check constraints control activity types,
expense categories, source/reference combinations, block status and positive amounts.
Unique `(created_by, request_key)` constraints prevent duplicate create retries.
Indexes cover farm/date history, plot/block/crop filters, task/visit/booking links,
and activity-linked expenses.

Context triggers reject cross-farm/plot/block/crop/task/visit/booking combinations,
enforce exact activity-linked expense context, and keep ledger sources/context
immutable. Crop context cannot change after an activity or expense references it.
Block farm/plot identity is immutable. This preserves historical attribution.
API context validation additionally controls ownership and active-block/assignment rules.

## F. Blocks

Farmers can create/list/edit/deactivate their own blocks. Name/description/area and
status are editable with a matching `expected_updated_at`; moving a block to another
plot/farm is not supported. Areas use acres, hectares or square metres. No area-sum
constraint exists. Inactive blocks remain visible in history but reject new crop
or ledger creation until reactivated. Existing plots/crops need no block.

## G. Activities

Controlled types: land_preparation, sowing_planting, irrigation, fertilizer,
pesticide, weed_management, labour, machinery, pruning, inspection,
harvest_support, transport, repair, other.

Sources: manual, crop_task, field_visit, service_booking. The source must match its
reference. No crop-task snapshot is copied into the activity. `harvest_support`
records work such as harvesting labour; there is no harvest event/yield/revenue record.

Create accepts explicit context or derives missing parent IDs from a selected
task/crop/block/activity. Supplied conflicting IDs are rejected rather than silently
overridden. Work does not require a plan or active/planted lifecycle status, so
preparation and historical work can be recorded without changing cultivation status.

Updates are full PUTs of editable factual fields with `expected_updated_at`.
Context/source links and creation attribution are immutable. Changes record
`updated_by` and a fresh timestamp; stale edits return 409. This is a correction
mechanism, not a complete versioned accounting audit trail. No delete API is added.
The optional performer ID may identify the caller; other workers can be described
in notes without inventing accounts or assigning work to unrelated users.

## H. Expenses

Controlled categories: seed_planting_material, fertilizer, pesticide, labour,
irrigation, diesel_fuel, machinery, repair, transport, harvesting, packing,
electricity, miscellaneous.

Expenses may stand alone or reference an activity. Linked expenses inherit its
exact farm/plot/block/crop context; conflicting references are rejected. An activity
can have any number of separate expenses. Corrections to amount/date/category and
descriptive fields use optimistic concurrency; context/activity links stay fixed.

The list response includes `items`, `count`, `total_amount`, `currency`. The total
uses every record matching the filters, independent of pagination. Farm/block/crop
and date-range totals therefore use the same list API. There is no profit calculation.

## I. Crop Task → Record Work and retry behavior

The explicit Record Work form creates an actual-work record with `crop_task_id` and
`source_type=crop_task`. It does not mark the task complete or fabricate an expense.
Changing task status through the existing API also creates no activity automatically.

Every activity/expense create requires a client-generated UUID `request_key`.
The UI retains it while retrying the same open form. A transaction-level advisory
lock serializes concurrent requests, backed by the database unique constraint.
Identical retries return the same saved record with HTTP 200; the first insert
returns 201. Reusing the key with different submitted content returns 409. The
original request payload is retained solely to compare retries and is omitted from
responses. Separate actual events, even for the same task, must use new request keys.

After an uncertain network result, retry the unchanged form. If it was closed,
check history before opening a new form: a new form deliberately represents a new
event and gets a new key. Durable offline draft recovery is not part of this slice.

## J. Field Officer authorization

Officer APIs require the existing `field_officer` capability and an explicit active
assignment to the referenced crop. There is no farm-wide officer access. Officers
can read that crop's activity history and create factual activities in it; they
can edit only their own activities while authorized. Visit-linked recording/editing
requires their own in-progress visit. Assignment closure serializes with activity
creation; losing access prevents subsequent reads/writes. Farmers retain history.

Farmer APIs require farmer capability and ownership. Field-officer capability alone
cannot read/create/edit expenses or retrieve financial totals. A multi-capability
officer who is separately a farmer can access only their own farm finances through
the normal farmer APIs. Admin capability does not impersonate a farmer or officer.
Provider-only accounts gain no access. Verification state is never modified.

Activities describe performed work, not agronomist advice. There are no prescription
or recommendation endpoints/fields. Free-text notes are for facts; this is not an
automatic content-classification or diagnosis system.

## K. Harvest-date validation fix

Expected harvest must be strictly later than actual planting, or the planned crop's
expected planting anchor when no actual planting date is present. Equality is rejected.
Applied to managed create, edit, activation and plan generation, and legacy crop
creation. Existing saved dates are not rewritten. Planned crops without a recorded
expected planting date remain valid; the comparison becomes enforceable once both
dates are supplied. A planned crop is never auto-activated.

## L. APIs added

| Method | Route | Access / behavior |
|---|---|---|
| POST | `/my/farm-blocks` | Farmer, owned farm/plot |
| GET | `/my/farm-blocks?farm_id=&plot_id=` | Farmer, own farm; includes inactive history |
| PUT | `/my/farm-blocks/{id}` | Farmer; edit/deactivate with `expected_updated_at` |
| POST / GET | `/my/farm-activities` | Farmer; create / filtered history |
| GET / PUT | `/my/farm-activities/{id}` | Farmer; owned detail / factual correction |
| POST | `/my/crop-tasks/{task_id}/record-work` | Farmer; explicit retry-safe actual work |
| POST / GET | `/my/farm-expenses` | Farmer; create / history and totals |
| GET / PUT | `/my/farm-expenses/{id}` | Farmer; owned detail / correction |
| GET / POST | `/field-work/crop-cycles/{cycle_id}/activities` | Explicitly assigned officer; history / create |
| PUT | `/field-work/crop-cycles/{cycle_id}/activities/{id}` | Assigned officer; own factual correction |

Farmer history filters: `farm_id`, `plot_id`, `farm_block_id`, `farm_crop_id`,
`date_from`, `date_to`, `limit` (default 20, max 100), `offset`. Activities also accept
`crop_task_id`, `activity_type`; expenses also accept `activity_id`, `category`.
Reversed date ranges are rejected. Unowned list filters return no matching data;
unowned detail/mutations return 404. Missing capabilities return 403.

Existing managed crop create/PATCH accepts optional `farm_block_id`. Existing
routes, auth payloads and legacy user roles remain compatible.

## M. Frontend

- My Crops → Crop Cycle: Overview / Crop Plan / Activities / Expenses navigation.
- Track Myself opens actual activity recording without requiring an SOP.
- Crop Plan tasks offer Record Work into the same activity history.
- Activities: chronological mobile cards, type/date filters, quantity/unit, source,
  linked task detail, edit, and Add Expense per activity.
- Expenses: standalone or activity-linked entry, vendor/person, payment mode,
  notes, edit, category/date filters, pagination and totals over all matching pages.
- My Crops → Farm Activities & Expenses / Manage Blocks: select an owned farm,
  optionally create/edit/deactivate blocks, and filter farm history by plot/block.
- New Crop Cycle: optional active block selector under the selected plot.
- My Field Work: assigned crop/visit factual activities; no expense controls.

Existing mobile card/44px form control styling is reused. No marketplace redesign.
Expense activity selectors offer the latest 100 activities in the context; older
activities can be reached through the paginated activity history and Add Expense.

## N. Backend validation

**169 passed**: all **130 existing tests**, plus **39 new Slice 2B tests**.
The existing baseline includes 37 marketplace/onboarding regressions, 68 Slice 1
tests and 25 Slice 2A tests. No existing test was removed or weakened.

New coverage includes blocks/ownership/deactivation, optional blocks, manual work
without SOP/task, task linkage, idempotent retries and distinct events, stale edits,
cross-context rejection and database guards, standalone/multiple linked expenses,
decimal validation/totals, booking linkage without side effects, officer assignment
boundaries and financial restrictions, all harvest-date entry points, migration
data preservation, concurrent task/expense retries, conflicting edits, assignment
closure races and populated downgrade refusal.

Two pre-existing dependency warnings remain: Starlette's httpx TestClient usage and
AnyIO's BlockingPortal alias. No regression failures.

```powershell
# From backend
..\.venv\Scripts\python.exe -m pytest -q
```

## O. Frontend validation

Production build passed (48 modules). Lint exited zero with **14 pre-existing
warnings**, **no new warnings or errors**. Existing warnings concern React effects
and hook dependencies in App, AdminDashboard, BookingForm, FarmSetup, MyServices,
Notifications, SupplierAvailability, SupplierDashboard and SupplierEquipment.

```powershell
# From frontend; npm.cmd avoids the machine's PowerShell npm.ps1 policy restriction
npm.cmd run build
npm.cmd run lint
```

The browser tool returned no available browsers. Browser end-to-end and visual
mobile validation were therefore not performed; use the steps below.

## P. Deferred features

No Harvest Events, yield/harvest quantity, multiple harvests, sales/revenue/profit,
produce marketplace, perennial seasons, orchard lifecycle, trees/tags/tree costs,
rentals/adoption, certification, inventory, weather/AI, agronomist workflow,
prescriptions, receipt OCR, advanced accounting or payment settlement. No photo
upload changes, offline sync, automatic booking import/expenses or area-sum validation.
Booking linkage is supported by API only; the marketplace UI is unchanged.
Slice 2B is the stopping point.

## Q. Exact manual browser/mobile test steps

1. Restart the normal backend/frontend processes, then sign in as a farmer with a
   saved farm and plot. Open My Crops.
2. Choose Farm Activities & Expenses / Manage Blocks. Select your farm, add a block
   under a plot (e.g. North Orchard, optional 0.5 acres), edit its name, then return
   to My Crops. No block is required for any existing crop.
3. Add an active crop cycle on that plot, optionally select the block, and enter
   actual planting 02-Sep-2026 and expected harvest 02-Sep-2026. Saving must fail
   with the strict date error. Change expected harvest to 03-Sep-2026 and save.
4. In Overview choose Track Myself. Add an irrigation activity with today's date,
   description of actual work, optional quantity/unit and notes. Confirm it saves
   without selecting an SOP or generating a plan. Edit the description and verify
   the history reflects the correction.
5. On that activity choose Add Expense. Save ₹120.25 labour, then add another ₹80.50
   machinery expense to the same activity. In Expenses confirm total ₹200.75 and
   both records. Add a standalone ₹25 expense: total should become ₹225.75. Edit
   it to ₹30: total should become ₹230.75. Zero/negative/over-precision amounts
   must be rejected. Check date/category filters and totals.
6. Return to Farm Activities & Expenses. Check the same entries in farm and block
   totals. Add a farm-only activity and standalone expense; they must appear in
   the farm total but not in a selected crop/block total.
7. Create/select a second crop without a block and confirm recording works normally.
   Deactivate the first block in Manage Blocks: history stays visible, the inactive
   block is excluded from new crop selection, and new entries into it are rejected.
   Reactivate it to continue recording.
8. On a crop with a published matching SOP, open Crop Plan, preview and generate
   the plan. For a planned crop, use an expected planting date strictly before its
   expected harvest. Confirm generating does not activate the crop.
9. Click Record Work on a task and enter actual performed work. Save and confirm
   the new record appears in Activities with a Crop Task link. Open that link;
   planned instructions/status should still be unchanged. Add an expense explicitly
   if needed. Merely changing task status must create neither activity nor expense.
10. In browser developer tools, replay the successful Record Work POST with its
    unchanged body/request_key. Expect 200 with the same activity_id, and one history
    record. Change its description while keeping the key: expect 409. A genuinely
    separate work event uses a new form/new key. Repeat for expense retry safety.
11. As admin, use existing Manage Field Work to assign an officer and schedule a
    visit to the crop. As that officer, open the assigned crop and Record Activity.
    Start the visit and record visit-linked work; check that verification remains
    unverified until its separate verification action is used. No Expenses UI is
    exposed. Expense API calls with an officer-only account must return 403.
12. As farmer, confirm officer-created activities appear in the same crop history.
    A second unassigned officer and unrelated farmer must not read or mutate this
    farm's records. Close the officer assignment as admin: officer activity access
    stops, while the owning farmer retains the history.
13. At 360px and 390px viewport widths, check navigation, block selectors, activity
    and expense forms, long notes/task titles, errors, totals and pagination for
    readable controls without horizontal scrolling. Also repeat on desktop.
14. Smoke-test existing farmer/provider sign-in/onboarding, farms/plots, service
    listing/search, booking/reschedule, provider availability, payments/reviews,
    SOP publication/snapshots, crop lifecycle transitions, and field visits and
    observations. No old workflow should require a block or activity record.
