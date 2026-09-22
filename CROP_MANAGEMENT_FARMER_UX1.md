# Farmer UX Foundation (UX1)

## Scope and baseline

Used Slice 7, Slice 6 and Slice 2D reports, then inspected only the farmer
components and their existing API dependencies. Baseline: head `e9b438c4a607`,
378 backend tests, 14 frontend lint warnings.

**No migration required.** No backend, database, auth or API behavior changes.
No development data was edited. Existing cultivation records, catalogues,
assignments, marketplace, booking/payment rules and capability checks remain.
The complete backend suite runs against its guarded, distinct test database.

## Friction removed / before and after

| Journey | Before | Now |
| --- | --- | --- |
| Farm creation/onboarding | Save returned to marketplace/list | Opens saved farm; onboarding offers Continue after the required address is saved. Address failure still retries without creating another farm. |
| Plot/block creation | Returned to undifferentiated list | Scrolls to and highlights saved plot/block; sole or supplied plot is selected for block creation. New blocks no longer ask for status. |
| Start Crop | Farm/plot selected again; tracking choice only after save | My Farms and each plot open the shared Start Crop flow carrying context. Sole farm/plot auto-selected. Track Myself opens Overview; Use Crop Plan opens plan selection. |
| Season/planting | Existing date-based behavior | Preserved: explicit season start, backend-generated season, optional custom label/variety/source, planting question instead of technical status. No invented planting/harvest date. |
| My Crops | Separate small Open action, raw lifecycle labels | Whole card opens through an accessible button; Growing / Completed / Season Closed labels. Current/History and five workspace tabs retained. |
| Plan/task | SOP/version clutter; permanently open status forms | Friendly plan names, single edition auto-selected, edition metadata under Plan details. Task actions revealed on demand as buttons; required reasons retained. |
| Work | Blank description even for a known task | Task title prefilled; selected farmer activity type supplies description if extra detail is omitted. Other work still needs a description. Optional quantity/notes collapsed. Saved work is shown even outside current filters/pages. |
| Inputs/planting details | Unlisted variety text shown by default; extra input fields always open | Existing searchable catalogue/fallback retained; unlisted field shown when chosen or already populated. Optional application details collapsed. |
| Expenses | Known activity shown as disabled selector; extra fields always open | Known activity shown as context; optional vendor/payment/notes collapsed. Saved expense displayed directly. |
| Harvest/sale | Save reset list; manual total calculation | Saved harvest opens, saved sale and updated harvest context displayed regardless of pagination/date. Optional extras collapsed. Quantity × price calculates a read-only estimate with decimal half-up rounding; API remains authoritative. Lump-sum entry retained. |
| Overselling | Generic conflict | Available quantity displayed; local excess explained. Failed saves refresh availability through existing APIs. Editing a sale includes that sale's original quantity in availability. |
| Completion/next season | Technical wording | Complete Crop / Close Season, crop totals and friendly history labels. Existing reconciliation, unfinished-task cancellation and explicit next-season dates remain unchanged. |

### Form/default review

Farm/plot/block/crop/task/service category IDs are carried or selected, never
derived from display labels. Work, expense, harvest and sale dates retain today's
editable default. Agronomic dates remain explicit. Numeric controls remain for
areas, quantities, prices and amounts; existing enumerations/catalogue selectors
remain for types, categories, crops, varieties, products and units. Custom entity
names, addresses, optional descriptions and free-form legacy payment/work units
remain editable text: there is no existing corresponding controlled master to
reuse, and no geography or new master system was introduced.

Hidden optional fields retain their values; invalid fields reopen their containing
panel for correction. Field Officer descriptions remain required as before.
Booking already carries crop/task/farm/category context and saved address defaults;
its matching and form were inspected and left unchanged. Task completion remains
an explicit action independent of bookings, work, expenses and harvest records.

## Files changed

- `frontend/src/App.jsx`: pass farm/plot creation context into My Crops.
- `frontend/src/FarmSetup.jsx`: create/open navigation, contextual Start Crop,
  friendly crop status, onboarding continuation and touch-target adjustment.
- `frontend/src/CropManagement.jsx`: defaults, tracking choice/navigation,
  cards, labels, progressive task/crop actions and saved-record context.
- `frontend/src/CropManagement.css`: card hit area, focus/saved states,
  44px disclosures, responsive choice controls.
- `frontend/src/FarmLedger.jsx`: work defaults, optional details, saved-record
  display, known activity/farm context and saved block navigation.
- `frontend/src/CropInputs.jsx`: optional/fallback field presentation.
- `frontend/src/CropHarvests.jsx`: optional details, calculated totals,
  availability guidance and saved harvest/sale context.
- `frontend/src/ProductionLifecycle.jsx`: farmer-facing completion/season labels.
- `frontend/src/farmerLabels.js`: display-only labels; stable backend codes retained.
- `frontend/src/farmerUx.js`: sale estimate rounding and native-validation disclosure.
- This report and `CROP_MANAGEMENT_SLICE2D.md`: current farmer flow documentation.

## Validation

- Complete backend: **378 passed**, 2 existing dependency warnings, 87.10s.
  Includes existing auth/onboarding/provider, marketplace, booking, capability,
  crop lifecycle, scheduling, harvest/accounting and concurrency tests.
- No backend tests added: backend behavior did not change.
- Frontend production build: passed.
- Frontend lint: 0 errors, **14 pre-existing warnings**; no new warnings.
- One-off Node/Vite server-render smoke checks passed: task-title default,
  known-activity context, optional disclosures, accessible crop card, sale-edit
  availability, calculated/read-only total, half-up rounding including 0.1 × 0.15.
  No frontend test framework or dependency was installed.
- Interactive mobile/browser testing has **not** been executed. Build/render
  checks do not validate touch behavior or layout on devices; use the steps below.

## Manual mobile checks — repeat at 360px and 390px

At every step check duplicate selections, unnecessary typing/taps, horizontal
overflow, long labels, keyboard focus and comfortably tappable controls.

1. Register/sign in as Farmer with mobile and no email. Create the required farm
   and address. Confirm saved farm opens; Continue completes onboarding. Also
   simulate address-save failure and retry: only one farm should exist.
2. My Farms → Add Farm → save: created farm opens. Back → reopen that farm.
3. Add Plot → save: saved plot is highlighted/in view. Blocks → Add Block → save:
   plot is preselected, no new-status field, saved block is highlighted. Edit
   still supports deactivation.
4. On that plot, Start Crop: farm/plot are already selected. With multiple farms,
   change farm and verify plot/block choices reset correctly.
5. Choose Tomato, optionally a saved variety/source. Set season start and verify
   automatic year label. Choose Not yet planted and an expected planting date.
   No internal lifecycle/status configuration or invented dates should appear.
6. Choose Track Myself → Create: new crop Overview opens. Return to My Crops and
   tap the card background or keyboard-focus its Open button to reopen it.
7. Repeat creation with Use Crop Plan: opens plan selection. Select a plan,
   preview tasks, select edition only if multiple exist, generate. Planned crop
   stays planned and saved task dates follow existing Slice 6 scheduling.
8. Crop Plan → Record Work: task title/date/context prefilled. Add a catalogue
   input, quantity and unit; optional details stay collapsed. Save opens saved
   work under Activities; task status must remain unchanged.
9. Add standalone work: select Irrigation and save without extra description.
   Other requires description. Save a backdated record outside a date filter:
   the saved record must still be visible.
10. Book Service from a compatible task: category and crop/farm/task context
    remain fixed, select availability and saved address, book and return to crop.
    Provider completion alone must not complete task or create an expense.
11. Record Expense from work/booking: known activity shown, date/category/amount
    editable, optional vendor/payment/notes available. Save shows the expense.
12. Harvests → Record Harvest: today, quantity/unit; optional grade/wastage/notes.
    Save a backdated harvest: it opens even if outside the first list page.
13. Record Sale: sell 25 units at 12.50; estimated/saved total must be 312.50.
    Test lump-sum total with no unit price. Saved sale/updated harvest should show.
    Try overselling and a second-session competing sale; check available-quantity
    guidance. Correct an existing sale without falsely excluding its own quantity.
14. Task → Update task / Complete: choose completion and confirm explicitly.
    Partial/not applicable/cancelled require a reason; terminal tasks cannot be
    edited through invalid transitions. Optional-panel invalid fields reopen.
15. Overview → Record planting when actually planted, then Complete Crop:
    review totals, confirm. Incomplete tasks close under existing rules; saved
    work/costs/harvests/sales remain in History, with Completed wording.
16. Mango: use an existing perennial planting, enable seasons if needed, Close
    Season → Start Next Season. Verify proposed dates/automatic year range,
    correct dates if necessary, save → new season Overview. Original planting
    and previous-season records remain unchanged. My Crops Current/History
    must show Growing/Season Closed appropriately.

## Deferred / decisions

No blocker requiring a product decision. Interactive mobile acceptance remains
to be performed. No localization, GPS/geography, WhatsApp, reporting, new master
data, inventory/accounting, marketplace redesign or later-slice features added.
Existing free-text optional payment/work-unit fields can receive controlled
masters in a separate design if desired. Saved harvest context reads paginated
sale records using existing endpoints; server-side aggregate detail could be
considered later if very large per-harvest sale histories make that costly.
