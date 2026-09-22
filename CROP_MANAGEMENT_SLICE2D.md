# Slice 2D — My Crops navigation and context cleanup

Current farmer interaction updates are documented in
[Farmer UX Foundation](CROP_MANAGEMENT_FARMER_UX1.md): context-aware Start Crop,
create/open navigation, friendly lifecycle labels, compact task actions and saved
work/harvest/sale display. The workspace now retains five tabs: Overview, Crop
Plan, Activities, Expenses and Harvests. Slice 2D's Current/History structure remains.

## A. UX/navigation decisions

My Crops now opens on **Current**, alongside **History**. A crop is the working
context for Overview, Crop Plan, Activities and Expenses. The crop name, farm,
plot/block and status stay above the shared workspace navigation.

The primary landing action is **+ Start Crop**. The old global Farm Activities &
Expenses / Manage Blocks action and All cycles dropdown are removed from this
landing page. Existing data and operational APIs remain available.

## B. Files changed

- `frontend/src/CropManagement.jsx`: Current/History, compact cards, shared context,
  overview summaries and historical action presentation.
- `frontend/src/FarmLedger.jsx`: read-oriented history, secondary corrections,
  plot-scoped block controls and reusable farm-wide records entry.
- `frontend/src/FarmSetup.jsx`: Blocks under each plot; secondary farm-wide records.
- `frontend/src/CropManagement.css`: compact responsive navigation, active states,
  embedded farm controls and long-button wrapping.
- `backend/crop_management.py`: grouped list filter and saved block name.
- `backend/tests/test_crop_navigation.py`: three focused API regression tests.
- `CROP_MANAGEMENT_SLICE2D.md`, `README.md`: report and documentation link.

No previous migration, database record or existing test was rewritten.

## C. Current vs History

- Current: planned and active crops; default on entering My Crops.
- History: all non-current statuses, currently harvested and cancelled. The filter
  will also include a future completed status without adding it to today's lifecycle.
- Filtering occurs before pagination; pages cannot hide matching crops behind
  records from another group.
- Returning from a crop keeps the selected list view/page. Starting a new crop
  opens that crop and selects Current for the eventual return to the list.

Current cards use existing response fields for crop, farm/plot/block, status,
variety, planting date, approximate duration, expected harvest, next task and overdue
count. Unknown optional fields are omitted. History cards show simpler context,
season, final status, known dates and View History. No actual harvest date is
invented; the existing schema does not provide one.

No per-card expense calls or new analytics were added. The crop-list response
does not contain expense totals, so card totals are omitted.

## D. Crop detail hierarchy

One existing crop-detail container hosts:

**Overview → Crop Plan → Activities → Expenses**

Navigation uses two columns at phone widths and four on wider screens. The active
button is visually distinguished and exposes `aria-pressed`. The saved crop context
is always visible above it. Existing components/forms are reused.

## E. Overview

Existing crop summary and planting snapshots display farm, plot, optional block,
season, status, planting/expected harvest, variety/source/lot, total-duration and
first-harvest estimates where available, plus task progress and overdue count.

Two existing, bounded calls add total crop expense and the three most recent
activities, only while Overview is mounted. The expense total uses the existing
filtered total across all pages; no new aggregation endpoint exists. Loading/error
states do not pretend that unavailable data equals zero. Existing officer/visit/
observation visibility and planting-edit functionality remain available.

## F. Crop Plan reuse

Existing SOP selection/preview/generation, snapshotted plan/version information,
task status transitions and Record Work remain in the Crop Plan tab. No plan logic
is duplicated. Plan name/version and anchor date are visible with the tasks.

Existing task execution actions remain limited to active crops. Terminal history
does not show a primary Record Work action or lifecycle/plan-creation controls.
The existing harvested transition is preserved; no new harvest/completion assumption
or Harvest Event workflow was introduced.

## G. Activities scoping

The selected crop supplies farm_id, plot_id, optional farm_block_id and farm_crop_id
to the existing FarmLedger/ActivityForm. Farmers do not reselect the crop. History,
source/task links, multiple inputs, unlisted inputs, corrections and explicit
expense linkage continue to use Slice 2B/2C components and APIs.

History opens for reading. A secondary **Correct / add historical records** action
retains late-entry/correction functionality that the existing ledger APIs allow.
It does not reopen the crop or enable prohibited task lifecycle actions.

## H. Expenses scoping

Expenses receive the same selected crop context. The existing category/date/card
list, activity linkage, Add Expense, totals and correction logic are reused. Totals
cover all matching records, not just the visible page. No repeated farm/plot/crop
selection or new cost/accounting model is introduced.

## I. Block management relocation

Navigate **My Farms → open Farm → Plots → Blocks** on the desired plot. Existing
BlockManager is reused with the selected farm/plot prefilled and the plot fixed.
Create/edit/deactivate remain available; blocks remain optional and their IDs/data
are unchanged. Crop creation still selects optional existing blocks.

The previous farm-wide activity/expense functionality is preserved under the
collapsed **Farm-wide work & expense records** section in Farm Details. This is a
secondary entry for work/costs beyond one crop, not the primary My Crops workflow.
It loads only when opened. Existing legacy farm/plot/crop setup is preserved.

## J. Track Myself

A crop with no SOP remains usable. Track Myself opens Activities, and Expenses is
available directly. Crop Plan offers optional existing plan setup; absence of an
SOP does not block work or expense recording.

## K. Use Crop Plan

Published SOPs generate the existing crop tasks. Record Work creates the existing
actual activity, including optional multiple/unlisted inputs, then opens Activities.
It does not change SOP content, verification, task status or create expenses implicitly.
Both modes share the same activity/expense history.

## L. Backend/API changes

Small additive query changes only:

- `GET /my/crop-cycles?view=current|history` filters before existing pagination.
  Existing farm/plot/crop/status filters can still be combined; ownership is unchanged.
  Omitting view preserves the previous all-status API behavior.
- Crop detail/list responses additionally return `block_name` through the existing
  block relation. Crops without blocks return null.

No new endpoint, domain table, analytics, status value or authorization system.
Existing crop-scoped activities and expenses APIs are reused unchanged.

## M. Migration status

**No migration required for Slice 2D.**

Guarded test and development databases both remain at **`f4c083d9b152`**, verified
read-only. No migration was created or applied and no block/crop data was moved.

## N. Backend tests

**212 passed**: all **209 existing tests** plus three focused navigation API tests.
New coverage checks grouped status mapping, filtering before pagination, unchanged
all-status compatibility, status intersections, authorization, invalid view values
and optional saved block names.

All marketplace/onboarding/Slice 1/2A/2B/2C regressions pass. Two pre-existing backend
dependency warnings remain: Starlette/httpx TestClient and AnyIO BlockingPortal alias.

```powershell
# From backend
..\.venv\Scripts\python.exe -m pytest -q
```

## O. Frontend build/lint and verification

Production build passed (50 modules). Lint exited zero with the same **14 existing
warnings**, **no new warnings/errors**. The existing warnings concern React effects
and dependencies in App, AdminDashboard, BookingForm, FarmSetup, MyServices,
Notifications, SupplierAvailability, SupplierDashboard and SupplierEquipment.

Rendered-markup checks using the installed Vite/React server renderer passed for:
Current selected by default, History unselected, removal of the global action and
All cycles filter, current card summary/actions, read-oriented harvested/cancelled/
future-completed cards, and secondary historical ledger corrections. These checks
do not simulate browser clicks/effects or measure physical layout.

Source review confirmed the shared workspace and unchanged crop-scoped ledger
context, Crop Plan and Track Myself reuse, and block entry placement. The browser
tool reported no available browser, so visual/mobile interaction checks remain manual.

```powershell
# From frontend
npm.cmd run build
npm.cmd run lint
```

## P. Exact manual browser/mobile checklist

1. Restart normal frontend/backend processes. Sign in as a farmer and open My Crops.
2. Verify Current is selected by default and Start Crop is the primary action.
   No All cycles dropdown or global Activities/Expenses/Manage Blocks action appears.
3. Confirm only planned/active crops appear. Check crop/plot/block/variety, available
   dates, duration, next task and overdue indicators. Reclick Current: the list
   should remain populated. Check pagination if there are more than 20 records.
4. Open History. Confirm harvested/cancelled records appear, with simpler cards
   and View History. Switching tabs resets to the first page.
5. Open a historical crop. Inspect its plan/tasks, activities, inputs, expenses and
   officer records. No task execution/plan creation/lifecycle controls should appear.
   Verify historical ledger corrections are secondary and do not reopen the crop.
6. Return to Current and open an active crop. Confirm crop/farm/plot/status stay
   visible above Overview, Crop Plan, Activities and Expenses.
7. In Overview, check planting snapshot/source/season/duration/first-harvest details,
   task progress, overdue count, crop expense total and recent activities. Refresh
   errors should be recoverable without losing the crop context.
8. Open Crop Plan. Confirm saved SOP/version, anchor date, tasks, statuses and
   existing allowed task lifecycle controls still work.
9. Choose Record Work on a task; enter actual work and optionally multiple listed
   or unlisted inputs. Save.
10. Verify Activities opens with that record, its task/source link and input history.
    Crop/farm/plot should not need to be selected again. The SOP/task snapshot and
    verification state must remain unchanged.
11. Add a manual activity in the same crop, without a task. Check chronological
    placement, optional inputs and editing.
12. Open Expenses and add a test expense (e.g. ₹100), optionally linked to that
    activity. Confirm category/date/amount/link and automatic crop context.
13. Confirm total crop expense increases by exactly the saved amount; check Overview
    after returning to it. Date/category filters and pagination must retain correct
    totals. An unrelated crop must not display these records.
14. Open a planned/active Track Myself crop without an SOP. Activities and Expenses
    must work immediately. Crop Plan should offer optional setup without blocking
    these tabs. Do not generate a plan merely to test manual recording.
15. Return to My Farms, open a farm, and choose Blocks on a plot. Confirm the correct
    plot is fixed, its saved blocks load, and add/edit/deactivate still work. No
    block is required for an existing plot/crop.
16. In Farm Details, expand Farm-wide work & expense records. Confirm old farm-level
    records remain accessible there, separately from the primary crop workflow.
17. Set browser viewport to 360px, then 390px. Check two-column navigation, selected
    tab states, readable cards, long variety/block/task/input text and touch targets.
18. Check for horizontal overflow on the landing page, all four crop tabs, forms,
    history, and plot Blocks section. Repeat on desktop. Finally smoke-test existing
    marketplace/auth/onboarding/provider/booking/availability/payment/review flows.

## Q. Deferred items

No Harvest Events or multiple-harvest workflows, revenue/sales/profit, orchard or
perennial seasons, trees/rental/adoption, agronomist workflow, inventory, weather/AI,
new design system or database restructuring. No new card expense aggregation or
invented actual lifecycle dates. Slice 2D is the stopping point.
