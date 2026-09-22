# Slice 6 — Season-based crop planning and stage scheduling

## Architecture and compatibility decisions

The universal production-season container remains `farm_crops`. Slice 4 already
introduced `period_started_on`, which now serves seasonal crops as well as
perennial seasons. No `production_cycles`, second crop-cycle entity, stage engine,
or parallel work history was introduced. `perennial_plantings` still identifies
the permanent planting; each season has its own existing `farm_crops` ID.

Season start means when planning/work for this season begins. It is not inferred
from record creation, planting, harvest, or today. A seasonal season can start
before planting. A perennial season can start years after permanent planting.
Permanent planting dates and previous seasons remain unchanged.

The existing snapshot chain is retained:

`SOP template → version → SOP tasks → plan → crop tasks`.

Phase, task type and optional marketplace service category are separate fields.
Task execution continues to use generated tasks. Stage/condition/manual tasks
are intentionally actionable without automatic date or stage activation; the
farmer determines when their saved instructions apply. They are not treated as
automatically detected agronomic events.

## Exact schema changes

Migration **`d8a327b3f596`**, from inspected actual head **`c7f216a2e485`**.

| Table | Change |
| --- | --- |
| `farm_crops` | Reuse existing nullable `period_started_on`; add nullable `expected_planting_on date` |
| `sop_tasks` | Add nullable `phase varchar(20)` with controlled vocabulary check |
| `crop_tasks` | Add nullable `phase varchar(20)` with the same check |
| `crop_cycle_plans` | Make `anchor_date` nullable; add nullable `season_start_snapshot date`, `expected_harvest_snapshot date` |

No new tables. All five added columns are nullable without defaults/backfill.
Historical phase, planting expectations, dates and actors are not fabricated.

The phase vocabulary is `pre_season`, `planting`, `crop_stage`, `harvest`,
`miscellaneous`. The first is displayed as **Pre-season** for perennial crops and
**Pre-plantation** for seasonal crops. There is no post-harvest phase: preparation
for the next season belongs in that next season.

Scheduling checks allow the seven types below, require nonnegative offsets only
for the four relative schedules, and require stage/condition content only on its
corresponding type. Date-relative generated tasks require a due date. Classified
stage/condition/manual tasks must have NULL due dates.

The existing SOP publication guard retains identity, retirement, and published
content immutability. Its publication predicate now accepts non-planting schedules
when the admin has explicitly supplied a task phase. This keeps old reserved,
unclassified drafts unpublished until reviewed, and preserves all existing tests
and published versions. The admin form requires a phase for new/edited tasks.

An additional database trigger protects all generated plan fields and generated
task content/scheduling fields. Only task status/note/completion/latest-update
audit fields may change. Existing service-requirement immutability remains.

A crop date trigger validates newly supplied/changed dates, without scanning or
rewriting historical date combinations. Expected harvest must follow season start
and expected planting; for non-perennial crops, season start cannot follow
actual/expected planting. Established perennial identity/date protections remain.

Existing plan uniqueness, task uniqueness, owner/crop indexes, task due-date
indexes, perennial period indexes, and booking/ledger retry indexes are reused.
No new phase search endpoint or redundant index was added.

## Season labels and next-season suggestions

- Seasonal/unknown lifecycle: deterministic start year, e.g. `2026`.
- Perennial: start year and following two-digit year, e.g. `2026-27`.
- No regional Kharif/Rabi assumptions or seeded crop/service/stage data.
- Normal farmer forms show the derived label; an optional correction is inside
  a disclosure. Server-side generation is authoritative when label is omitted.
- Updating season start updates a previously generated label. Explicit custom
  labels are retained unless the caller supplies a correction.
- A planting detail response includes `next_season`: the previous latest season
  start's calendar anniversary and its derived label. February 29 becomes
  February 28 in the following non-leap year. No suggestion exceeds year 9999.
- Start Next Season prefills this proposal, permits date adjustment, and sends
  the confirmed start plus the existing UUID request key. The backend derives
  the label when omitted. It still requires the previous season to be closed
  and the new start to be later than all previous starts.
- Existing named seasons and historical labels are not relabelled by migration.

## Scheduling semantics

| Type | Generated due date | Required input |
| --- | --- | --- |
| `days_after_season_start` | season start + offset | Saved `period_started_on` |
| `days_before_planting` | planting reference − offset | Actual or explicit expected planting |
| `days_after_planting` | planting reference + offset | Actual or explicit expected planting |
| `days_before_harvest` | expected harvest − offset | Saved `expected_harvest_on` |
| `crop_stage` | NULL | SOP-defined `crop_stage_key`, copied unchanged |
| `condition` | NULL | SOP-defined `condition_text`, copied unchanged |
| `manual` | NULL | No offset, stage, or condition |

The planting reference is still internally `anchor_date`. An active crop uses its
actual `planted_on`; a conflicting explicit anchor is rejected. A planned crop
uses saved `expected_planting_on`, or an explicitly supplied legacy plan anchor.
A supplied conflicting saved expectation is rejected. Nothing defaults to today.
Season-only and undated plans do not require a planting date. For an established
perennial, an available permanent planting date may remain in the plan's planting
reference, but season tasks never calculate dates from it.

New classified plans require season start. If a date-relative task lacks its
anchor, generation fails atomically with an explanation; it does not create a
partial plan or silently leave that task unscheduled. Calculated classified task
dates before season start and date overflow are rejected. Choose a suitable SOP
or correct the season's dates before generation.

Legacy unclassified days-after-planting SOPs retain their old calculations,
including old perennial dates before current season start. Historical legacy
requests without a recorded season start continue to require an explicit anchor.
Existing plans/tasks do not change. No task is retrofitted with a guessed phase.

Stages are SOP-defined using the existing persisted `crop_stage_key`; farmers
read the saved stage and never type a stage during execution. There is no global
hardcoded lifecycle or automatic stage-state machine. A future crop-specific
master/label association can extend this existing stage key without replacing
generic tasks. Conditions are readable instructions, not evaluated expressions.

## Generation, retries, status and overdue

Generation keeps the existing crop-row lock, template/version lock, published
and crop-match checks, and single transaction. The plan captures season start,
planting reference and expected harvest. Each task copies phase, schedule, offset,
stage/condition, content, type and service requirement/name. Its due date is
calculated once. One plan per `farm_crops` and task uniqueness remain enforced.

Same-version retries return the saved plan with 200 (first create 201), including
after closure or subsequent date correction. A conflicting explicit anchor or
different version returns 409. Omitting an anchor on a season-plan retry uses the
saved plan; it never recalculates dates. Creation/date edits serialize on the crop
row, so a plan contains one coherent date snapshot.

New classified tasks can be updated while the season is planned or active. This
lets pre-plantation work be recorded/completed without falsely activating the
crop. Legacy unclassified tasks retain their original active-crop requirement.
The existing status-transition map, required notes, terminal statuses and explicit
completion action remain. Undated tasks are actionable but never overdue.

Overdue remains derived from due date + open task status + current India date,
for active crops and classified tasks in planned seasons. Closed seasons are
never overdue. No persisted overdue status or time-based background mutation.

Changing expected dates or season dates never moves generated tasks. Detail
responses expose planting/season date mismatch indicators, shown in Overview.
Established perennial season identity stays immutable under Slice 4's rules.

## APIs and authorization

| Existing API | Additive behavior |
| --- | --- |
| `GET /crops` | Also returns existing lifecycle/group/harvest metadata for correct farmer label preview |
| `POST /my/farms/{id}/crop-cycles` | Optional `period_started_on`, `expected_planting_on`; derives omitted season label |
| `GET/PATCH /my/crop-cycles/{id}` | Read/correct season dates within existing lifecycle/identity rules |
| Admin SOP task POST/PATCH | Optional controlled `phase`; seven validated scheduling types |
| Admin SOP publish/clone | Classified extended schedules accepted; all fields copied; published content immutable |
| SOP discovery/preview | Existing endpoints expose saved phase/stage/schedule fields |
| `POST /my/crop-cycles/{id}/plan` | Schedule-specific date validation and immutable date/task snapshots; planting anchor optional where appropriate |
| Plan/task GETs | Phase, stage, optional due dates, date snapshots/mismatch flags and derived overdue |
| `POST /my/crop-tasks/{id}/status` | Classified tasks actionable in planned seasons; existing transitions retained |
| `POST /my/crop-cycles/{id}/enable-seasons` | Season label can be omitted and generated |
| `GET /my/perennial-plantings/{id}` | Adds `next_season` date/label proposal |
| `POST /my/perennial-plantings/{id}/seasons` | Omitted label generated from confirmed start; existing retry/one-open-season rules |

No new routes or auth mechanism. Admin SOP mutations require effective admin
capability. Farmer mutations/reads require farmer capability and farm ownership;
other farmers receive 404. Catalogue access retains its existing authenticated
access. Provider completion still grants no farmer/task write authority.

## Frontend

- Start Crop: explicit date-picker season start, automatic season label with
  optional correction, optional expected planting, existing actual-planting choice.
- Existing variety-duration suggestion may use seasonal expected planting.
  Perennial start does not suggest harvest from its years-old permanent planting.
- Overview: season dates editing for current crops, expected planting display,
  saved-plan mismatch notices. Existing five tabs and Track Myself remain.
- Admin SOP editor: separate phase, type and optional category; all seven
  schedules; SOP-defined stage/condition inputs and undated-task explanation.
- Plan preview/cards: correct schedule/phase/stage/condition; no claim that all
  tasks are days after planting. Dated tasks remain ordered by due date, undated
  tasks follow in SOP sequence. No invented due date is displayed.
- Known planting dates are reused. A planting input is shown only when the SOP
  requires it. Next-season start and label are proposed automatically.
- Uses existing responsive cards, date pickers and CSS. No marketplace redesign,
  new styling framework, localization framework or dependency.

## Slice 5 and operational history

`Crop Task = planned work`, `Booking = marketplace fulfilment`,
`Farm Activity = actual work`, `Farm Expense = actual cost` remain unchanged.

Season-based tasks with an existing category use the original booking engine,
availability/capacity checks, booking origin and retry keys. Provider completion
creates no activity, expense, verification or task completion. Farmer Confirm
Work creates exactly one linked activity; cost is separately confirmed; task
completion is explicit. The task card now permits that explicit completion for
classified preparation tasks in planned seasons.

Cancellation/rejection leaves the task actionable. New linked work/bookings are
rejected for closed periods. Historical retries and authorized corrections retain
existing rules. Closing a season still cancels unfinished tasks atomically and
does not secretly cancel marketplace bookings. Next seasons receive separate
plans/tasks/bookings; permanent planting and prior work/cost/harvest/sale records
are never copied or reassigned.

## Files changed

Backend:

- `backend/season_planning.py` (new deterministic helper module).
- `backend/crop_management.py` (existing models, generation and task rules).
- `backend/production_lifecycle.py` (generated labels and next-season proposal).
- `backend/main.py` (three existing metadata fields in crop-list response only).
- `backend/alembic/versions/d8a327b3f596_season_planning.py` (new migration).
- `backend/scripts/verify_slice6_migration.py` (guarded migration/data verification).
- `backend/tests/test_season_planning.py` (new).
- `backend/tests/test_season_planning_concurrency.py` (new).
- `backend/tests/test_crop_management_concurrency.py` (only fixture schema setup
  extended; original test assertions retained).

Frontend: `frontend/src/CropManagement.jsx`, `SopManagement.jsx`,
`ProductionLifecycle.jsx`, `TaskServices.jsx`, `cropApi.js`.

Documentation: this report, README, and forward notes in Slice 1/4/5 reports.
No old migration files, dependencies, declarative ORM, or broad main.py refactor.

## Validation and data preservation

- Full backend suite: **348 passed** in 81.70 seconds — all **316 existing tests**
  plus **32 new tests** (29 behavior/integration cases and 3 concurrency/migration
  cases). No existing assertion was removed or weakened.
- Command from `backend`: `..\.venv\Scripts\python.exe -m pytest tests -q`.
- Two existing dependency deprecations remain: Starlette/httpx TestClient and
  AnyIO BlockingPortal alias. No new backend warnings.
- Final frontend `npm.cmd run build`: **passed**, 53 modules; JS 438.14 kB,
  gzip 114.18 kB. `npm.cmd run lint`: **passed**, no errors, the same **14 existing
  warnings**, none in the changed Crop Management components.
- Guarded test database: migrated to **d8a327b3f596**, downgrade/reapply passed;
  all **45 pre-existing tables** retained row counts and original-column data
  fingerprints. New columns on existing rows remained NULL.
- Guarded development database: migrated to **d8a327b3f596** after validation;
  all **45 pre-existing tables** retained row counts and original-column data
  fingerprints. New columns on existing rows remained NULL. No development
  downgrade or historical data patch occurred.
- Test setup initially caught a redundant constraint removal in the downgrade;
  it was corrected before the successful test downgrade/reapply and development
  apply. Two initial legacy compatibility failures were fixed; the final full
  suite has no regressions.
- Browser/mobile interactive testing was not performed; follow the manual flows
  below. The production build validates bundling, not interactive behavior.

New tests cover all seven schedules; missing/invalid anchors; expected-vs-actual
planting; automatic/custom labels; calendar/leap-year next starts; permanent
planting preservation; independent perennial task and booking history; phase/stage
snapshots, clone and published/SQL immutability; preparation-task updates; derived
overdue; Track Myself; closed-season work rejection; one confirmed booking activity;
no automatic completion/expense; request retries; generation races/date-edit races;
and populated-downgrade refusal. Existing tests retain legacy and marketplace,
auth/onboarding, ledger, harvest, sale, officer and provider coverage.

The verifier checks the explicitly selected local database, distinct test name,
actual connection identity and prior head. It compares every original column's
ordered data fingerprint plus table row counts, excluding only Alembic tracking.
No historical date/phase backfill, data reset or ad-hoc record patch is performed.
Test downgrade/reapply is exercised only when no new season-planning history
would be lost. Populated downgrade is refused; development is never downgraded.

## Manual browser tests

Restart backend after migration and reload frontend. Use catalogue crops and real
existing service categories/providers; no example crop/category is seeded.

### Seasonal crop (Paddy, or another configured seasonal crop)

1. Admin: create/clone a draft SOP for the crop. Add tasks with instructions:
   pre-plantation preparation, `days_after_season_start` + 2; planting,
   `days_before_planting` − 1; crop-stage inspection with a crop-appropriate stage;
   harvest, `days_before_harvest` − 3; optional condition/manual tasks. Assign the
   preparation task an existing category used by a verified provider. Publish.
2. Farmer: My Crops → Start Crop. Select farm/plot/crop. Season start June 1,
   expected planting June 20, expected harvest October 1, 2026. Verify season
   `2026` appears without typing; planting has not happened. Save opens that crop.
3. Use Crop Plan → select/preview the SOP → Generate. Verify tasks due June 3,
   June 19 and September 28, and stage/condition/manual tasks with no due date.
   Crop remains planned. Refresh/retry: only one plan and its task set.
4. Record preparation work before planting. Complete that task explicitly;
   verify crop remains planned. For the mapped service task, Book Service with
   actual available slots. Verify correct crop/farm context and unchanged task
   status; use a separate trial crop/task if the preparation task is already done.
5. Provider performs normal Confirm → Start → Complete at the permitted real
   times. Farmer refreshes service status: no automatic work or expense appeared.
   Confirm Work, retry, and verify exactly one activity. Record actual expense,
   then explicitly Complete Task. Also test cancellation/rebooking on a fresh task.
6. Overview: record actual planting June 20. Complete stage/condition/manual tasks
   when appropriate; they never display an invented due date. Correct an expected
   date and verify saved task dates stay unchanged with a mismatch notice.
7. Record harvest/sale using existing screens; close the crop. Verify history,
   totals and unfinished-task cancellation. Closed crop cannot start new task
   bookings/work. Repeat Track Myself without generating any plan.

### Perennial crop (Mango, configured Orchard / Perennial)

1. Admin: publish a Mango SOP with pre-season pruning/preparation at season start
   + 2, a crop-stage task such as Flowering, and a harvest-relative task. Use an
   existing applicable service category on one task. No planting-relative offset
   should substitute for an annual-season schedule.
2. Farmer: Start Crop with actual permanent planting May 10, 2011, season start
   September 1, 2026, expected harvest in 2027. Verify `2026-27` automatically.
   For an existing planting record, use Overview to set/enable its explicit season.
3. Enable Seasons in Overview, confirming the prefilled current season start.
   Generate its plan. Preparation is due September 3, 2026, not in 2011. Flowering
   is visible without a date. Permanent planted_on stays May 10, 2011.
4. Exercise Book Service → provider completion → Confirm Work → optional expense
   → explicit task completion. Check Activities/Expenses belong to this season.
5. Record harvest/sales, then Close Season. Inspect retained tasks/work/totals.
   From the perennial planting choose Start Next Season. Verify September 1, 2027
   and `2027-28` are proposed; adjust the date if intended and save.
6. The new season opens with the same permanent planting date and an independent
   empty operational history. Generate its own plan; preparation is now due
   September 3, 2027. Create a booking and verify it appears only on that season's
   task. The old plan/bookings/costs/harvests remain in old-season history.
7. Attempt another simultaneous open season and cross-farmer access: reject.
   Check 360px/390px and desktop layouts, error recovery, optional label correction,
   date pickers, undated task cards, and navigation after creation.

For real marketplace testing, choose available current/future slots and let normal
provider time restrictions apply; do not bypass clocks to force completion.

## Known limitations and deferred items

- No automatic stage activation/condition evaluation, plan regeneration, automatic
  rescheduling, weather/readiness engine, or regional season calendar. Dates remain
  farmer decisions. Future advisory inputs can reference the same farm_crop season
  without controlling those dates or replacing the model.
- Legacy unclassified tasks preserve active-only execution and historical planting
  calculations. To use seasonal scheduling, publish a reviewed draft with phases
  and generate a plan for a crop that does not already have one.
- Stage labels are SOP content; a shared crop-stage master and localized display
  labels can be introduced later. No new logic depends on English crop names.
- Established perennial season identity is still immutable. A correction workflow
  for that identity or plan rescheduling needs separate design.
- API clients may omit season start for backward-compatible legacy/Track Myself
  records; the normal new farmer UI requires it, and classified plan generation
  requires it. No automatic repair of old missing dates.
- Browser/mobile interactive testing remains manual; build/lint and API tests are
  not a substitute for the documented end-to-end checks.

Stopped after Slice 6. No WhatsApp, GPS/LGD, Telugu rollout, bulk import/export,
reporting, Super Admin, managed farming/landowner, agronomist/officer signup,
livestock, tree tracking, produce expansion, weather/AI, new payments, inventory,
or unrelated marketplace/farmer UX redesign was implemented.
