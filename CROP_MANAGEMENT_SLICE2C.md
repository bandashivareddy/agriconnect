# Crop/Farm Management Slice 2C — implementation report

## A. Architecture decisions

The schema contained no equivalent variety, planting-source or input-product
entities. Four additive tables now provide these concepts without replacing the
existing crop, activity, expense, SOP or marketplace structures.

Planting identity is optional. A small JSON snapshot retains the selected variety
name/type/duration estimates and source name/brand/type/notes. Changing master
data does not relabel historical plantings. Explicitly changing the selected
variety/source refreshes only that snapshot component; editing the lot or expected
harvest does not refresh either component.

Actual input usage belongs to an activity, inherits its context, and snapshots its
selected product information. Quantities are execution facts; money remains in
`farm_expenses`. Planned SOP/task content and officer verification remain separate.
There is no new verification or accounting system.

For missing catalogue entries, an unlisted variety is local planting text; an
unlisted product is stored in that activity's input snapshot with `is_unlisted=true`.
Neither creates an unverified global master record. No real companies/products are
hardcoded or seeded by the migration.

## B. Reused structures

Existing SQLAlchemy Core/parameterized SQL, engine and JWT/effective capabilities,
farmer ownership, officer assignments and in-progress visit rules, farms/plots/blocks,
`farm_crops`, SOP-generated `crop_tasks`, retry-safe activities, existing expenses,
strict Pydantic request conventions, audit timestamps and guarded Alembic tooling.
Frontend uses existing mobile cards, 44px controls and `useCropApi`.

## C. Files changed

Added:
- `backend/alembic/versions/f4c083d9b152_crop_inputs.py`
- `backend/farm_inputs.py`
- `backend/tests/test_crop_inputs.py`
- `backend/tests/test_crop_inputs_concurrency.py`
- `frontend/src/CropInputs.jsx`
- `frontend/src/FarmCatalogueAdmin.jsx`
- `CROP_MANAGEMENT_SLICE2C.md`

Updated:
- `backend/crop_management.py`: optional planting identity/snapshots and crop metadata in detail responses.
- `backend/farm_ledger.py`: optional atomic activity inputs and officer input-edit eligibility.
- `backend/main.py`: register the additive catalogue/usage router.
- `frontend/src/CropManagement.jsx`: planting selection, history, edit and duration suggestions.
- `frontend/src/FarmLedger.jsx`: multiple draft inputs, saved input history/corrections.
- `frontend/src/App.jsx`, `frontend/src/AdminDashboard.jsx`: admin catalogue entry.
- `README.md`: documentation link.

No previous migrations, baseline SQL, or existing tests were edited. No ORM
conversion or broad main.py refactor.

## D. Migration

One new revision: **`f4c083d9b152`**, parent **`e3b072c8a941`**.
Applied and verified first on the guarded local test database, then development
after validation passed. Both heads and all four new tables verified. Existing
development table row counts and every pre-existing crops/farm_crops field value
were compared before/after and preserved. No temporary test schemas remain.

From repository root, for another correctly configured local environment:

```powershell
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target test
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target development
```

No manual SQL is needed for normal upgrade. Downgrade refuses to discard populated
catalogue/input history, planting information, or crop metadata.

## E. Crop catalogue changes

Nullable controlled fields on `crops`:
- `crop_group`: orchard / seasonal / vegetable.
- `lifecycle_type`: seasonal / perennial.
- `harvest_pattern`: single / multiple / recurring.

Existing rows stay unclassified rather than receiving inferred classifications.
Admins can edit metadata; farmer Crop Cycle overview displays the group/lifecycle
when available. These labels do not activate different crop/harvest workflows.

## F. Crop varieties

`crop_varieties` stores crop FK, name, optional controlled type, optional default
planting-source FK, separate duration and first-harvest ranges, notes, active/inactive
status and audit actors/timestamps. Variety types: hybrid, open_pollinated, cultivar,
clone, local, other. Varieties cannot move between crops.

A partial unique index on crop + normalized case/whitespace name prevents duplicate
active varieties. Duration estimates are nullable positive integers up to 36500
days; minimum cannot exceed maximum. Unknown/perennial durations may remain blank.
An inactive variety remains referenced by history but cannot be newly selected.

`farm_crops` adds nullable `crop_variety_id`, `planting_material_source_id`,
`seed_or_material_lot`, `variety_text`, and `planting_snapshot`. A composite FK
enforces variety/crop agreement. Listed variety and unlisted text are mutually
exclusive. Existing records are not backfilled with invented information.

## G. Planting material sources

`planting_material_sources` has source name, optional brand, controlled source type,
notes, active/inactive status, and audit metadata. Types: seed_company, nursery,
tissue_culture_supplier, farmer_saved, local_supplier, other.

This is a generic source catalogue, not a seed-company-only model. Varieties may
have a default source; the farmer can explicitly choose that default, search for
another active source, or leave source blank. An inactive source is unavailable
for new selection but historical snapshots remain readable.

## H. Duration and first-harvest behavior

Separate fields/windows represent total crop duration and days to first harvest.
The suggestion endpoint adds stored day estimates to an explicitly supplied
planting date. The frontend uses the selected variety or saved planting snapshot
and the actual planting date, or a saved plan's expected planting anchor.

No date is written automatically. Buttons explicitly choose a total-duration or
first-harvest window end date; farmers can enter/override their own date. Unknown
bounds are displayed as unknown, not inferred. Crop creation still works without
these estimates. The existing strict rule remains: expected harvest must be after
actual/expected planting when both dates exist. Plan generation does not activate
a crop. This is scheduling metadata, not agronomic advice or a harvest event.

## I. Farm input catalogue

`farm_input_products` stores input type, commercial product name, optional brand,
manufacturer, active ingredient, formulation, labelled nutrient composition,
default unit, notes, status and audit metadata. Controlled types: fertilizer,
pesticide, fungicide, herbicide, bio_input, growth_regulator, soil_amendment,
micronutrient, other. Seed is not a separate input type here.

Admins create/edit/deactivate entries. Search covers product name, brand,
manufacturer and active ingredient. Farmer/officer selectors return active entries
in pages of 20, with debounced search. They do not load the entire product or variety
master. Existing references retain snapshots after master edits/deactivation.

## J. Fertilizer representation

Optional `nutrient_composition` is a JSON object of explicitly labelled percentages.
Supported keys: N, P, K, P2O5, K2O, S, Ca, Mg, Zn, B, Fe, Mn, Cu, Mo. Each value must
be finite and between 0 and 100. P and P2O5, or K and K2O, are kept distinct; there
is no automatic conversion, deduction from a product name, or chemistry engine.
The admin form accepts this small JSON object and explains the label-only rule.

## K. Pesticide/chemical representation

Product name, brand, manufacturer, active ingredient and formulation remain
separate fields, and are copied into actual usage snapshots. Product-name search
and active-ingredient search both work. No dosage, pesticide/fertilizer recommendation,
certification or residue-compliance logic is added.

## L. Farm Activity → Actual Inputs

`farm_activity_inputs` contains:
- activity FK; optional product FK (null only for a local unlisted product).
- immutable `product_snapshot` and `is_unlisted` marker.
- positive `numeric(14,4)` quantity and controlled unit: kg, g, L, ml, tonne, unit.
- optional actual application method, target/reason and notes.
- creation/update actors/timestamps, request key and original request payload.

No farm/plot/block/crop IDs are duplicated into this table. Product/context/audit
identity is protected by an update trigger. Product and activity FKs preserve
history. Quantity/unit/method/reason/notes can be corrected with optimistic
`expected_updated_at`; stale edits return 409. Identity cannot be silently replaced.
No hard-delete API or complete versioned correction-history UI is added.

An activity may have zero/multiple input records. A create request accepts up to
50 initial inputs atomically; more can be appended later through paginated input
APIs. Invalid/inactive products roll back the whole initial activity transaction.
Each separate input append requires a request UUID. The activity row lock and
unique `(activity_id, request_key)` make retries safe; identical replay returns
200/the same input, conflicting reuse returns 409. Input snapshot fields never
refresh from a mutable product catalogue during quantity correction.

## M. Expense integration

The existing `farm_expenses.activity_id` relationship is reused unchanged. An
activity can have multiple inputs and multiple expenses, or inputs with no expense.
Input quantities never create money records. There is no price catalogue, quantity
times price calculation, stock balance, purchase accounting or duplicate cost table.

## N. SOP / Record Work integration

The existing ActivityCreate/Record Work request optionally includes `inputs`.
Inputs are saved in the same transaction as the activity and are covered by the
same idempotency payload; child retry keys are deterministically derived for this
initial batch. Empty/omitted inputs retain the previous request shape for old retries.
After a successful transaction, replay works even if the product is later inactive.

No input usage modifies SOP definitions, generated task snapshots, task status,
officer verification or expenses. Verification remains the existing Slice 2A
task/visit mechanism; recording inputs is not itself verification.

## O. Farmer UX

- New Crop Cycle: progressively disclosed optional variety/source/lot section,
  crop-filtered variety search, unlisted text, source search/default selection,
  separate duration/first-harvest estimates and explicit date-suggestion buttons.
- Crop overview: saved planting labels/lot/estimates and optional crop group.
- Open crop overview: edit planting details and expected harvest through the
  existing managed cycle PATCH route; closed-cycle edit rules remain unchanged.
- Add Activity / Record Work: add several draft input cards before saving atomically.
  The activity cannot be saved with an unfinished input draft.
- Activity cards: View / add actual inputs, labelled product history, pagination,
  append inputs and correct factual quantities/notes.
- Unlisted products remain local to the activity; an incomplete master catalogue
  never blocks actual-work recording. Existing legacy farm setup still works without
  requiring variety/source/input fields.

## P. Admin UX and APIs

Admin Dashboard → **Crop & Input Catalogue** provides varieties, planting sources,
input products and crop metadata. Master forms support create/edit/deactivate;
varieties can be filtered by crop. Master edits use `expected_updated_at` to reject
stale changes. Crop metadata is a small full PUT of optional classification labels.

| Method | Route | Purpose |
|---|---|---|
| POST / GET | `/admin/crop-varieties` | Create / search/filter varieties |
| PUT | `/admin/crop-varieties/{id}` | Edit/deactivate |
| POST / GET | `/admin/planting-material-sources` | Create / search sources |
| PUT | `/admin/planting-material-sources/{id}` | Edit/deactivate |
| POST / GET | `/admin/farm-input-products` | Create / product/ingredient search |
| PUT | `/admin/farm-input-products/{id}` | Edit/deactivate |
| PUT | `/admin/crops/{id}/metadata` | Optional group/lifecycle/harvest labels |
| GET | `/catalogue/crops` | Paginated crop search including metadata |
| GET | `/catalogue/crop-varieties` | Active variety search, optional crop_id filter |
| GET | `/catalogue/planting-material-sources` | Active source/brand search |
| GET | `/catalogue/farm-input-products` | Active product/brand/manufacturer/ingredient search |
| GET | `/catalogue/{master-path}/{id}` | Active variety/source/product detail |
| GET | `/catalogue/crop-varieties/{id}/duration-suggestion?planting_date=` | Separate duration and first-harvest windows |
| GET / POST | `/my/farm-activities/{activity_id}/inputs` | Owned input history / retry-safe append |
| PUT | `/my/farm-activities/{activity_id}/inputs/{id}` | Factual correction |
| GET / POST | `/field-work/activities/{activity_id}/inputs` | Assigned officer history / permitted append |
| PUT | `/field-work/activities/{activity_id}/inputs/{id}` | Permitted officer correction |

Master search uses `q`, `limit` (default 20, maximum 100) and `offset`; varieties
also use `crop_id`, products use `input_type`. Admin lists additionally accept
active/inactive `status`; public catalogue endpoints always restrict to active.
Input histories default to 50 per page, maximum 100.

## Q. Field Officer behavior

Officers can select active catalogue products and record actual inputs when
creating their own assigned-crop activity, including their in-progress visit work.
They can read input history within a current explicit assignment, but may append
or correct inputs only on activities they are authorized to modify under Slice 2B:
their own activity, and their own in-progress visit when visit-linked.

Completing/cancelling a visit closes officer input edits for its activity. Closing
the assignment removes officer input access; farmer history remains. Officers do
not receive farmer financial access, automatic farmer impersonation or prescriptions.

## R. Authorization and validation

Existing capability helpers are reused. Admin manages masters; farmer/officer/admin
can read active catalogues. Provider-only users gain no catalogue or crop access.
Farmer usage APIs enforce activity farm ownership. Officer usage APIs lock/check
active assignment, visit and activity in the established order. Admin capability
alone does not grant farmer input mutation access.

Enforced: variety/crop consistency, valid active selections, mutually exclusive
listed/unlisted choices, controlled types/statuses/units, positive precise finite
quantities, positive ordered duration ranges, nonblank names, source existence,
cross-farm/actor boundaries, immutable input identity, and stale-edit conflicts.
Unknown product/variety IDs are not accepted merely because an activity/crop exists.

Unlisted text records facts; no NLP prescription detector or automatic diagnosis
is introduced. Catalogue composition and input quantities are not recommendations.

## S. Backend results

**209 tests passed**: all **169 existing tests** plus **40 new Slice 2C tests**.
No existing regression was removed or weakened. Coverage includes varieties and
normalized duplicates, crop/source/lot selection, snapshot stability, missing/inactive
entries, duration windows/overrides, product identity/search/composition validation,
multiple/unlisted input usage, correction safety, atomic rollback, expense separation,
SOP preservation, ownership/officer restrictions, migration preservation and real
concurrent retries/deactivation/duplicate creation.

Two pre-existing dependency warnings remain: Starlette/httpx TestClient and AnyIO's
BlockingPortal alias. Marketplace/onboarding/Slice 1/2A/2B regression tests all pass.

```powershell
# From backend
..\.venv\Scripts\python.exe -m pytest -q
```

## T. Frontend results

Production build passed (50 modules). Lint exited zero with **14 pre-existing
warnings**, **no new warnings or errors**. Existing warnings concern React effect
state/dependencies in App, AdminDashboard, BookingForm, FarmSetup, MyServices,
Notifications, SupplierAvailability, SupplierDashboard and SupplierEquipment.

```powershell
# From frontend
npm.cmd run build
npm.cmd run lint
```

The browser tool returned no available browsers/apps. Browser end-to-end and mobile
visual verification were not performed; the following manual steps remain necessary.

## U. Deferred features

No Harvest Events, harvest quantities/multiple-harvest UI, sales/revenue/profit,
inventory/purchase orders/warehouses/stock deduction, price catalogue, agronomic or
dosage recommendations, AI/weather, organic certification/residue compliance,
produce marketplace, perennial production seasons, tree management/rental/adoption,
receipt OCR or advanced accounting. No automatic nutrient/unit conversion or
input-cost calculation. No full master-data versioning system: history uses small
snapshots. Stop after Slice 2C.

## V. Exact manual browser/mobile test steps

1. Restart the usual backend/frontend processes. Sign in as admin and open
   **Crop & Input Catalogue**. In Crop metadata, select an existing crop and set
   an appropriate optional group/lifecycle/harvest pattern; save.
2. In Planting material sources, create a test nursery/source with an optional
   brand. In Crop varieties, select that same crop and create a test variety with
   total duration 130–150 days and first harvest 70–80 days. Optionally choose the
   test source as default. Save. An identical case/space-normalized active variety
   name for that crop must be rejected. A minimum above its maximum must fail.
3. In Farm input products, create two clearly labelled test products. For one,
   enter a small valid labelled nutrient JSON object; for another, enter distinct
   commercial name, brand, manufacturer, active ingredient and formulation. Search
   by each useful field and confirm results. No price/dose field should exist.
4. Sign in as the farmer. My Crops → Add Crop Cycle → select farm/plot/crop and an
   optional block. Expand Variety, source and lot. Search/select the test variety,
   explicitly choose a source/default source and enter a lot/batch.
5. Choose Active and planting date 10-Jun-2026. Confirm total-duration window
   18-Oct–07-Nov and first-harvest window 19–29 Aug display separately. Enter expected
   harvest 01-Oct-2026; choosing the variety must not overwrite it. A suggestion
   button changes the date only when clicked. Entering 10-Jun as expected harvest
   must fail; use a later date and save.
6. Confirm overview shows selected snapshot labels/lot/estimates and metadata. Edit
   the lot and expected harvest. Then, as admin, rename/deactivate the selected
   variety/source. Return to the saved crop: original labels/estimates must remain.
   Existing lot/date edits should still work without refreshing these snapshots.
7. Create another crop without variety/source, and another with unlisted local
   variety text. Both must work. Wrong-crop/inactive varieties must not appear in
   normal selection. No perennial duration is mandatory.
8. In Activities → Add Activity, enter factual work, then Add Input. Search/select
   test product A, enter a positive quantity/unit and optional actual method/reason.
   Add a second product before saving. Confirm one activity and two input cards are
   saved; no expense or task-status change is created automatically.
9. Use View / add actual inputs on that activity. Add a local unlisted product and
   confirm it is marked unlisted and does not appear in the global master. Correct
   a quantity/notes field. Product identity should remain fixed. Zero/negative/
   non-finite/over-precision quantities and unsupported units must be rejected.
10. As admin rename/deactivate a used input product, changing its composition or
    ingredient label. Existing activity input cards must retain their original
    product/ingredient/formulation/composition details. Inactive products should
    disappear from new searches; new selection by an old ID must fail.
11. Add two existing expenses to the same activity. Confirm existing totals and
    activity links work and neither expense is calculated from an input quantity.
    Inputs must also work on an activity with no expense at all.
12. From a generated Crop Plan task choose Record Work and enter multiple actual
    products. After saving, verify SOP/task instructions, task execution status and
    field verification remain unchanged. Actual products appear under Activities.
13. In browser developer tools replay the successful activity POST unchanged,
    including its request_key and inputs: expect 200, same activity, no duplicated
    inputs. Repeat an append-input POST with its request_key: same input returns.
    Reusing a key with altered content must return 409. Use a new form/key for a
    genuinely separate usage event.
14. As an assigned officer, create an activity with inputs on the assigned crop.
    Start a scheduled visit and record visit-linked activity inputs. Verify an
    unassigned officer cannot access them, and an assigned officer cannot alter
    farmer-created activity inputs. Complete the visit: officer edits close.
    Close the assignment: officer reads/writes stop, farmer history remains.
    Officer-only expense API requests must still return 403.
15. At 360px and 390px widths, check progressive planting details, search/results/
    pagination, long names/ingredient text, multiple draft input cards, errors,
    saved input history and expense controls without horizontal overflow. Repeat
    on desktop. Browser visual checks have not been automated in this session.
16. Smoke-test existing auth/onboarding, farms/plots/blocks, provider services,
    bookings/rescheduling/availability/payments/reviews, SOP publication/generation,
    task/crop lifecycle, officer observations/verification and activity/expense
    corrections. No existing workflow should require variety/source/input data.
