# Crop Management Slice 1

## Scope and persistence

Crop Cycles are existing `farm_crops` records. No `crop_cycles` table exists.
Migration `c901a7b2d310` adds nullable `created_at`, `updated_at`, `created_by`,
`updated_by` to `farm_crops`, without defaults/backfill on historical rows.
The five new tables are `sop_templates`, `sop_versions`, `sop_tasks`,
`crop_cycle_plans`, and `crop_tasks`.

Only days-after-planting schedules can be published/executed in Slice 1. Other
approved schedule types can be stored in drafts. Published version content and
its task membership are protected by PostgreSQL triggers. Retiring a version
prevents new plans but does not affect existing snapshots.

Plan generation requires an explicit expected planting date (planned crop) or
actual planting date (active crop). Internally this is `anchor_date`. For an
active cycle with `planted_on`, the dates must match. Generation never activates
a planned crop or supplies today's date. One plan per cycle is enforced by a
unique constraint; identical retries return the saved plan, even after retirement.
Activation after a different actual planting date shows a schedule mismatch;
this slice does not regenerate or shift existing tasks.

Task execution reads snapshots. Statuses: pending, in_progress, completed,
partial, not_applicable, cancelled. Partial/not-applicable/cancelled require a
note. Overdue is derived for unfinished tasks on active cycles using the India
business date. Harvest and cancellation close unfinished tasks atomically;
harvest appends a system explanation and preserves previous notes and terminal
tasks. There is no harvest quantity/revenue accounting.

## API reference

Paths below are backend paths; Vite exposes them under `/api`.
All `/my` routes require farmer capability and ownership through the farm.
Provider-only accounts are excluded; users with both capabilities retain access.
Admin SOP routes accept effective admin capability, including legacy admin role.
Admin SOP authority does not grant private farmer-cycle access.

| Method | Path | Purpose |
|---|---|---|
| GET | `/my/crop-cycles` | Own cycles; farm_id, plot_id, crop_id, status, limit/offset filters |
| POST | `/my/farms/{farm_id}/crop-cycles` | Create cycle in farm_crops |
| GET, PATCH | `/my/crop-cycles/{id}` | Details/edit allowed metadata; crop/plot frozen after plan |
| POST | `/my/crop-cycles/{id}/status` | Lifecycle transition using expected_status |
| GET, POST | `/my/crop-cycles/{id}/plan` | Read/generate immutable plan and snapshots |
| GET | `/my/crop-tasks` | Own tasks; cycle_id, status, due_from/due_to, limit/offset |
| GET | `/my/crop-tasks/{id}` | Task snapshot/current state |
| POST | `/my/crop-tasks/{id}/status` | Transition using expected_status and optional/required status_note |
| GET | `/sop-templates` | Farmer discovery; optional crop_id |
| GET | `/sop-templates/{id}/versions` | Available published versions |
| GET | `/sop-versions/{id}` | Published SOP preview |
| GET, POST | `/admin/sop-templates` | List/create templates |
| PATCH | `/admin/sop-templates/{id}` | Edit name/description/active flag; crop immutable |
| GET, POST | `/admin/sop-templates/{id}/versions` | List/create draft; optional clone_from_version_id |
| GET, PATCH | `/admin/sop-versions/{id}` | Inspect/edit draft version_notes |
| POST | `/admin/sop-versions/{id}/tasks` | Add draft task |
| PATCH, DELETE | `/admin/sop-tasks/{id}` | Edit/delete draft task |
| POST | `/admin/sop-versions/{id}/publish` | Validate and publish |
| POST | `/admin/sop-versions/{id}/retire` | Retire published version |

Bodies are strict: identity/actor IDs come from authentication. IDs belonging to
another farmer return 404. Capability failures return 403. Validation failures
return 422; stale state and immutable-resource conflicts return 409. Generation
returns 201 initially and 200 on an identical retry. No delete API is provided
for plans, crop tasks, cultivation history, templates or versions.

Task transition map:
- pending -> in_progress/completed/partial/not_applicable/cancelled
- in_progress -> completed/partial/not_applicable/cancelled
- partial -> in_progress/completed/cancelled
- completed/not_applicable/cancelled are terminal

Cycle transition map:
- planned -> active/cancelled
- active -> harvested/cancelled
- harvested/cancelled are terminal

## Migration and automated validation

From the project root, migrate test first:

```powershell
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target test
.\.venv\Scripts\python.exe backend/scripts/migrate_local.py --target development
```

The helper checks local host, distinct test-named database and the actual target
connection. The historical untracked test schema was compared with the tracked
development schema before stamping its existing optional-email revision. No
baseline SQL was rerun. Both databases are now at `c901a7b2d310`.

Normal tracked environments can use `alembic upgrade head` from `backend`.
Downgrade refuses to discard populated Crop Management/audit history.

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

From `frontend`:

```powershell
npm.cmd run build
npm.cmd run lint
```

Validated: 105 tests passed (37 existing + 68 new). New tests include the entire
task transition matrix, ownership, scheduling, snapshots, rollback injection,
legacy audits and area behavior, and four real concurrency scenarios. Regular
Crop Management fixtures roll back all records. Concurrency tests create and
remove disposable schemas only in the guarded test DB; no schemas remain.
Frontend build passed. Lint has 14 existing React-hook warnings, no new warnings
or errors. Backend has two existing Starlette/httpx/AnyIO deprecation warnings.
Browser-driven visual/E2E testing was unavailable because the connected browser
inventory was empty. Use the following manual steps to verify the screens.

## Manual end-to-end checks

1. Restart the backend and frontend using the existing launcher, or the existing
   uvicorn/Vite commands. Open `http://localhost:5173`.
2. Sign in as an existing admin. Click **Manage Crop SOPs**.
3. Under **Create SOP template**, select an existing crop, enter `Slice 1 Trial`
   and a description, then create it. The template should become selected.
4. Click **New empty draft**. Add three tasks, all scheduled **days after planting**:
   - Sequence 1, `Inspect emergence`, inspection, offset 0.
   - Sequence 2, `Irrigate field`, irrigation, offset 2.
   - Sequence 3, `Inspect leaves`, pest_monitoring, offset 4.
   Provide instructions for each. Edit a draft task and save version notes.
   Add/delete an extra draft task to verify deletion before publication.
5. Publish the version. Its edit/add/delete controls should disappear. Click
   **New draft from this version** and verify an independent draft/version number.
   Leave that draft unpublished for now.
6. Sign out and sign in as a farmer. If necessary, complete existing onboarding.
   In **My Farms**, create a plot if the farm has none. Return to marketplace.
7. Open **My Crops** -> **Add Crop Cycle**. Select the farm, plot and same crop.
   Choose **Planned** and an expected harvest date after your planting date.
   Create the cycle. Confirm it remains planned and has no actual planting date.
8. Select `Slice 1 Trial` and its published version. Inspect the task preview.
   For this test, explicitly enter a date seven days before today as the expected
   planting date and generate the plan. Check task dates equal that date plus
   0/2/4 days. Refresh/reopen: one plan and three tasks
   should remain, and the cycle should still be planned.
9. Activate the cycle with the same date (seven days before today) as its actual
   planting date; keep expected harvest in the future. Unfinished tasks before the current India date should be overdue.
   If actual planting differs from the plan date, a mismatch notice should appear;
   existing task dates must not silently move.
10. Complete task 1. Mark task 2 partial with a note such as `Half the field done`.
    Leave task 3 pending. Verify completed/total, next-task and overdue summaries.
11. Change the cycle to **harvested**, despite unfinished tasks. Task 1 must remain
    completed with its completion metadata. Tasks 2 and 3 must become cancelled
    with the harvest explanation; task 2 must retain its earlier partial note.
    All three records remain visible and overdue count becomes zero.
12. Create another **Active** cycle with an actual planting date. Its generation
    date field should use that date and be read-only. Generate its plan.
13. As admin, retire the published version. Existing farmer plans still display
    their original instructions. A new cycle must no longer offer that version.
    Publish the cloned draft; it should become separately selectable.
14. Confirm draft-only unsupported schedules: create a draft task with `manual`
    or `condition` scheduling. It can be saved, but publication must clearly fail
    until all tasks use days-after-planting scheduling.
15. At a 360–390px viewport, check forms, task cards, buttons and status controls
    for horizontal scrolling and readable labels.
16. Regression smoke check: farmer My Farms/plots/existing crops and booking flow;
    provider dashboard/services/availability; existing payment and review flow.
    Sign in with a second farmer and confirm the first farmer's cycles are absent.

## Intentionally deferred

No staff roles, assignments, visits, photos/observations, irrigation/fertilizer
execution records, expenses, harvest quantities/revenue, profitability, booking
links, produce marketplace, weather/AI, or plot-area-sum validation. Plan
regeneration/rescheduling, task reopening and full append-only task audit events
are also deferred. Current audit fields describe creation/latest update and
completion; harvest notes preserve unfinished-task closure reasons.


## Slice 6 scheduling update

See [CROP_MANAGEMENT_SLICE6.md](CROP_MANAGEMENT_SLICE6.md) for season-start planning, automatic season labels and classified stage/condition/manual tasks. The earlier slice behavior above describes its historical baseline; existing saved plans remain unchanged.
