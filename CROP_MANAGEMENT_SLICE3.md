# Slice 3 — Harvest Events + Revenue

## Scope and behavior

An existing `farm_crops` cultivation instance can have any number of harvests,
and a harvest can have multiple sales. Recording or correcting either never
changes crop status, planting dates, plans or task states. Planned, active and
historical crops retain their existing lifecycle rules. Historical entries and
corrections are permitted for the owner and explicitly authorized admins.

The crop supplies farm, plot and optional `farm_block_id`; forms do not ask for
this context again. Existing legacy crops without a plot remain supported.
Seasonal, vegetable and orchard/block crops use the same harvest model.

## Files changed

- `backend/alembic/versions/a5d094e0c263_harvest_revenue.py` — additive migration.
- `backend/harvest_management.py` — validation, Core SQL routes and summaries.
- `backend/main.py` — imports and registers the new router only.
- `backend/tests/test_harvest_management.py` — 34 API/data-integrity cases.
- `backend/tests/test_harvest_concurrency.py` — 8 transaction/migration cases.
- `frontend/src/CropHarvests.jsx` — harvest/sale cards, forms and summary.
- `frontend/src/CropManagement.jsx` — fifth tab and Overview financial summary.
- `frontend/src/CropManagement.css` — five columns on wider crop navigation;
  two columns retained on phones.
- `README.md` and this report.

No existing migrations or tests were rewritten. No dependency changes.

## Migration and schema

Revision `a5d094e0c263`, following `f4c083d9b152`.

`harvest_events`: identity ID, crop/farm/optional plot/block foreign keys,
harvested_on, quantity numeric(14,4), controlled unit, optional grade,
wastage_quantity and notes; required actor/timestamp audits and UUID create
request key plus immutable original JSON payload.

`harvest_sales`: identity ID, restrictive harvest foreign key, quantity_sold
numeric(14,4), same unit as harvest, optional price_per_unit numeric(14,4),
total_amount numeric(14,2), sold_on, optional buyer_name/notes, same audit and
retry fields. All monetary values are INR, matching existing expenses.

No columns are added to existing tables. No old rows are backfilled or edited.
New indexes cover crop/date harvest lists, farm/plot/block references and
harvest/date sale lists. Unique actor/request-key constraints prevent duplicate
creates. Foreign keys prevent deleting referenced history.

Checks/triggers enforce positive finite quantities/amounts, nonnegative wastage
no greater than harvested quantity, matching crop context, immutable source and
creation audit, sale units/dates, and aggregate sold quantity no greater than
harvested minus wastage. A crop's physical/crop identity cannot be changed after
harvest history exists; lifecycle transitions remain permitted. Existing block
identity protections are reused.

Populated downgrade refuses to delete harvest/sale history. Empty downgrade and
upgrade are tested in a disposable guarded test schema.

## API contract and authorization

Each route below exists under both `/my/crop-cycles/{cycle_id}` and
`/admin/crop-cycles/{cycle_id}`:

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | `/harvests` | Date-descending cards with sold, available and revenue totals |
| POST | `/harvests` | Record harvest with inferred context |
| GET | `/harvests/{event_id}` | Read one harvest |
| PUT | `/harvests/{event_id}` | Correct factual harvest fields |
| GET | `/harvests/{event_id}/sales` | Date-descending sales |
| POST | `/harvests/{event_id}/sales` | Record sale |
| PUT | `/harvests/{event_id}/sales/{sale_id}` | Correct factual sale fields |
| GET | `/harvest-summary` | Quantities by unit, revenue, expenses and net return |

`/my` requires farmer capability and farm ownership. `/admin` requires admin
capability and records the actual admin actor. Provider-only and officer-only
accounts have no access. Cross-crop and cross-harvest IDs return 404. Missing
authentication returns 401. Context fields supplied in request bodies are
rejected; the authorized crop is the only source of context.

List endpoints return arrays, accepting `limit` (1–100, default 20) and `offset`.
Create returns 201; identical retry returns 200. Every create needs a UUID
`request_key`, retained by the frontend form. Reusing the key for different
details/context returns 409. A replay after correction returns the current
saved record without undoing the correction. PUT follows existing full factual
record correction conventions and requires `expected_updated_at`; stale edits
return 409. Invalid input returns 422; database history/quantity/date/unit
conflicts return 409. No delete APIs were introduced.

Mutations lock crop then harvest before writing; retries also use transaction
advisory locks. Database sale triggers lock the parent harvest and enforce the
aggregate quantity even for direct SQL. All writes are transactional.

## Quantity, money and correction rules

Units: `kg`, `g`, `tonne`, `quintal`, `unit`, `crate`, `box`, `bag`, `bunch`.
No implicit conversion or guessed container weight. Summary `quantities` is an
array with `unit`, `total_harvested_quantity`, `total_wastage` and
`total_sold_quantity`. Different units are never added into a misleading total.

Sales use the harvest unit and cannot predate their harvest. Enter a total
amount directly, or supply a price per unit to calculate it. If both are given,
they must agree using decimal multiplication and half-up rounding to paise.
Calculated amounts outside the supported range are rejected before insertion.

Corrections cannot reduce sellable quantity below existing sales, change a
harvest's unit after sales exist, or move harvest date after a saved sale. Correct
the relevant factual sale first if needed. Records are retained with updated
actor/time; this follows existing ledger auditing, not a new revision-history
system.

Summary also returns `total_revenue`, `total_expenses`, `net_return`, `currency`.
Costs come only from existing `farm_expenses` linked to this crop. Independent
aggregates avoid multiplication across joins. Unsold produce has no assigned
revenue. Farm-wide overhead is not allocated. Net may be negative. This is
recorded sales less recorded crop costs, not cash collection or a full profit
accounting system.

## Frontend

Farmer: My Crops → Open Crop / View History → Harvests.
The workspace now has Overview, Crop Plan, Activities, Expenses and Harvests.
Harvests contains quantity/financial summary, paginated cards, Record Harvest,
Record Sale, sale history and factual corrections. History initially hides
editing behind “Correct / add historical records”, as existing ledger UI does.
Overview shows expenses, revenue and net return plus recent work. Returning to
Overview fetches fresh totals. Forms retain their create key on retry; errors
are displayed and refresh is available. Admin management is available through
the explicit API namespace; no new admin screen was requested.

## Validation

Migration applied to both guarded local test and development databases, each
verified at `a5d094e0c263`. All 42 pre-existing development tables retained
identical row counts and complete data fingerprints across the migration; new
harvest tables were empty. Disposable concurrency-test schemas were cleaned up.

- Full backend: **254 passed**, including all **212 existing** and **42 new** tests.
- Command: from `backend`, `..\.venv\Scripts\python.exe -m pytest tests -q`.
- Two pre-existing dependency deprecations: Starlette/httpx TestClient and
  AnyIO BlockingPortal alias. No new backend warnings.
- Frontend `npm.cmd run build`: **passed**, 51 modules transformed.
- Frontend `npm.cmd run lint`: **passed**, zero errors, the same **14 pre-existing
  warnings** in App, AdminDashboard, FarmSetup, SupplierEquipment,
  SupplierAvailability, SupplierDashboard, Notifications, MyServices and BookingForm.
  No new warnings in the Crop Management files.
- Existing auth/onboarding/marketplace/booking/availability/payment/review and
  earlier Crop Management tests remain green. Browser regression checks below
  remain manual.

New tests cover 42 cases: repeated/no-plot/block/historical harvests,
unchanged lifecycle/tasks, invalid quantities/wastage/amounts, partial/multiple
sales, rounding, unit/date mismatches, overselling, correction/stale behavior,
retry conflicts, authorization, context isolation, grouped quantities, expense
isolation/net loss, pagination, direct SQL guards, actual concurrent transactions,
additive migration preservation and downgrade safety.

React server-render checks cover forms, no repeated context selectors, unit/date
labels, quantity and financial formatting, historical actions and workspace
imports. These do not substitute for interactive browser testing. No browser
was exposed by the session; manual checks below remain required.

## Exact manual end-to-end checks

1. Restart the backend after migration and open the frontend. Sign in as a farmer.
2. Open My Crops → an active crop → Harvests. Confirm correct crop/farm/plot/block
   context and all five tabs. Note the current crop status and task progress.
3. Record harvest: date September 1, 2026; 100 kg; grade A; wastage 10 kg; notes.
   Confirm status/task progress did not change and 90 kg is available.
4. Record sale on that card: September 2, 2026; 30 kg; price ₹50; leave total
   blank; optional buyer. Confirm revenue ₹1,500 and available 60 kg.
5. Add another sale: 40 kg; total ₹2,000; price blank. Confirm total sold 70 kg,
   revenue ₹3,500 and available 20 kg. Expand View Sales to see both entries.
6. Attempt a sale of 21 kg. Confirm an error and unchanged saved totals. Try a
   zero amount, a sale before harvest, and conflicting price/total; none may save.
7. Add crop expense ₹120.25 on Expenses. Return to Overview: on a fresh test crop,
   expenses ₹120.25, revenue ₹3,500, net ₹3,379.75. Check Harvests matches.
8. Record a second harvest of 50 kg. Confirm multiple cards and 150 kg harvested,
   10 kg wastage, still-active status. Add 2 crates as a third harvest and verify
   crates and kg appear separately.
9. Correct a sale's buyer/amount; verify totals update. Try reducing the first
   harvest's sellable quantity below 70 kg or changing its unit: reject both.
   Open the same record in two tabs, save one, then save the stale tab: reject it.
10. Test slow/retried Save requests: only one harvest/sale should be created.
    Check errors preserve typed fields. Refresh to recover from stale edits.
11. Separately mark the crop harvested using its existing Overview status action.
    Confirm existing unfinished task closure behavior, with harvests/sales retained.
    Open History → crop → Harvests; use “Correct / add historical records” to
    correct a record or add a late entry. Crop must remain harvested.
12. Repeat recording on an orchard crop with a block and on a crop without an SOP.
    No extra farm/plot/block/crop selectors or plan requirements should appear.
13. Sign in as another farmer/provider/officer: the first farmer's new endpoints
    must deny access. An admin token can use the documented `/admin` routes.
14. At 360px and 390px widths, check all five tabs, cards, both forms, validation
    messages and long notes/buyer names for readable wrapping, usable touch
    targets and no horizontal overflow. Repeat on desktop and check pagination.
15. Smoke-test sign-in/onboarding, farms/plots, marketplace/service booking,
    provider availability, payments and reviews through their existing screens.

## Deferred

Payment status/method and collection/settlement, produce marketplace, delivery,
subscriptions, task-to-booking links, leases/livestock/trees, advanced allocation,
inventory/unit conversion, weather/AI and unrelated features. Stopping at Slice 3.
