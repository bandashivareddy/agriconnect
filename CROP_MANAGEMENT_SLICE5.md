# Slice 5 — Crop Task → Service Booking → Work

## A–B. Existing architecture and integration decision

The marketplace uses `supplier_services` as bookable services and
`service_categories` as their classification; there is no separate base `services`
table to duplicate. The existing `/my/bookings` path creates one service item
per booking. It validates provider availability/verification, ownership, prices,
complete consecutive hourly slots and capacity, locks availability rows, then
creates `bookings`, `booking_items`, `booking_slot_reservations`,
`booking_status_history` and provider notifications in one transaction.

The integration adds an optional origin on the booking header. It uses that
same endpoint and transaction. It does not create a crop-specific booking table
or another availability, equipment, payment, review or status system. Existing
service/equipment associations and marketplace behavior remain intact.

`farm_activities` already had both task and service-booking foreign keys, but its
source check prevented using them together. This slice narrowly permits that
combination for confirmed task bookings. Activities remain actual work; crop
tasks remain planned work; bookings remain marketplace fulfilment.

## C–E. Schema, migration and optional service requirement

Migration **`c7f216a2e485`**, after `b6e105f1d374`.

Nullable additions:

| Table | Columns |
| --- | --- |
| `sop_tasks` | `service_category_id`, `service_category_name_snapshot` |
| `crop_tasks` | `service_category_id`, `service_category_name_snapshot` |
| `bookings` | `crop_task_id`, `crop_context_snapshot`, `crop_request_key`, `crop_request_payload` |

No new domain tables and no new activity/expense fields. Existing rows receive
NULL optional fields; no historical task mappings or booking origins are inferred.

Admins may select one existing active service category on a draft SOP task, or
leave it unset. There are no automatic task-type/category mappings. Matching
uses the exact category ID, not a mutable category name or guessed provider.
Choose the category actually assigned to supplier services; parent categories
are not automatically expanded into their descendants.

Category identity/name are saved with the draft, copied when cloning a version,
and snapshotted into generated crop tasks. Published SOP tasks remain protected
by the existing version immutability trigger. Generated task service requirements
have an additional immutability trigger. Renaming a category or changing a future
SOP never rewrites live/historical crop tasks.

Checks/FKs enforce paired optional fields, immutable booking origins, owned
actionable crop context and service-category matching. A unique farmer/request
key protects linked booking retries. A partial unique index allows one confirmed
task activity per service booking. Existing ledger source/context guards remain,
with the narrow service-booking + task combination added. New work must reference
the completed booking, owning farmer and same task/crop. Populated integration
history prevents destructive downgrade.

## F. Booking linkage and retries

`POST /my/bookings` accepts optional `crop_task_id` and `crop_request_key` UUID.
Both are needed for a linked create. Farm is inferred from the authorized task;
a supplied conflicting farm is rejected. Plot, block, crop, season, task name,
type, due date and saved requirement are captured server-side in the origin
snapshot. Clients cannot supply that snapshot. Existing booking validation then
runs without bypasses.

Matching services are retrieved through the existing `/services` endpoint using
its new optional `category_id` filter. Provider/service active and verification
rules still apply. The existing BookingForm selects actual time slots, address
and quantity; it displays fixed crop context instead of another farm selector.

Identical request retries return the same booking with HTTP 200 (first create
201), without extra items/reservations/history/notifications. Changed details
under the same key return 409. A fresh key represents an intentional new booking;
availability/capacity rules still apply. Idempotent replay remains possible after
cancellation or crop closure and does not recreate the booking.

## G–I. Confirmed work, expense and task completion

Provider completion uses the existing provider status endpoint and time checks.
It does **not** create an activity/expense, change field verification or complete
the crop task. Payment also remains separate.

The farmer chooses Confirm Work on the completed booking's task card. This reuses
ActivityForm and `POST /my/farm-activities`, with inferred context,
`source_type='service_booking'`, `crop_task_id` and `service_booking_id`. The farmer
confirms the actual date/type/description and optional quantities/inputs. No
scheduled date or estimated execution is silently asserted as actual work.

Existing actor/request-key replay protection applies. A second create with a
fresh key for the same task booking conflicts; corrections use the existing
activity edit flow. Preparation work may be confirmed while a crop is planned
or active, matching existing manual activity behavior. Closed seasons reject
new work through this linked flow; already-saved retry/correction history remains.

After confirmation, Record Expense reuses ExpenseForm and `farm_expenses` with
the saved activity link. Booking total is an editable suggestion, explicitly
labelled for farmer confirmation. No payment or estimated price automatically
creates a cost. Existing expense request keys prevent duplicate retries; multiple
intentional cost entries remain possible through the ledger. The task card shows
when an expense already exists.

Complete Task then calls the existing task-status endpoint, only after saved
booked work exists in this UI. It is a separate farmer action. Existing status
rules still require an active crop before task completion. Self-recorded work,
manual task status controls, Track Myself and field-officer verification retain
their existing behavior.

## J–K. Cancellation and crop/season boundaries

Cancelled/rejected bookings retain their history and never cancel the crop task.
Farmers can book again or record work themselves. Multiple bookings per task are
allowed for additional genuine work, with an existing-booking notice.

The task's plan identifies its exact `farm_crops` period. Seasonal crops,
vegetables and perennial seasons share the same integration. A next-season task
links to that new period, not the original orchard season. Closed periods cannot
receive new task bookings or linked confirmed activities. Closing a crop does
not secretly cancel its marketplace bookings; existing booking actions remain
the source of truth for those commitments.

## L–M. Files changed

Backend:

- `backend/task_services.py` — context, validation, retry and read helpers/router.
- `backend/main.py` — additive booking fields/hook, category-ID filter and origin
  fields on existing farmer/provider booking lists; router registration.
- `backend/crop_management.py` — draft requirement validation, clone and generation
  snapshots.
- `backend/farm_ledger.py` — narrow source validation and completed-booking guard.
- `backend/alembic/versions/c7f216a2e485_task_service_booking.py`.
- `backend/tests/test_task_services.py`.
- `backend/tests/test_task_service_concurrency.py`.
- `backend/tests/test_crop_management_concurrency.py` — fixture setup adds the new
  optional task fields after its deliberately old Slice 1 schema initialization.
  No existing test assertions were removed or weakened.

Frontend:

- `frontend/src/TaskServices.jsx` — optional actions, matched service selection,
  small live booking summaries and origin display.
- `frontend/src/SopManagement.jsx` — optional category on draft tasks.
- `frontend/src/BookingForm.jsx` — optional fixed crop context and retry key.
- `frontend/src/CropManagement.jsx` — service flow in Crop Plan and reused bookings.
- `frontend/src/FarmLedger.jsx` — optional confirmed booking and suggested expense.
- `frontend/src/MyBookings.jsx` — origin link and optional focused booking view.
- `frontend/src/SupplierDashboard.jsx` — read-only booking origin.
- `frontend/src/App.jsx` — route back to the originating crop.

Documentation: this report and README. No dependencies or existing migration
files changed; no broad main.py refactor.

## N. APIs added/changed

| API | Change |
| --- | --- |
| Existing admin SOP task POST/PATCH | Optional `service_category_id`; draft-only |
| Existing SOP clone / plan generation | Copy requirement snapshots |
| `GET /services?category_id=…` | Optional exact active-category filter |
| `GET /my/crop-tasks/{id}/service-context` | Owned context and whether a new booking is allowed |
| `GET /my/crop-tasks/{id}/bookings` | Owned live booking summaries, activity link and expense count |
| `POST /my/bookings` | Optional task origin + retry key; existing booking engine |
| Existing farmer/provider booking GETs | Read-only origin fields |
| `POST /my/farm-activities` | Confirm completed task booking through existing ledger |

Expense/task-status/payment/review/provider status endpoints remain unchanged.
Task context and booking reads require farmer capability plus ownership. Providers
see only the origin on their own existing booking cards and cannot write crop
records. Officer verification is neither automatic nor required by booking.

## O–S. Validation

- Full backend suite: **316 passed** — all **291 baseline tests** plus **25 new
  integration tests** (18 API/workflow cases and 7 concurrency cases).
- Command from `backend`: `..\.venv\Scripts\python.exe -m pytest tests -q`.
- Two unchanged dependency deprecations: Starlette/httpx TestClient and the AnyIO
  BlockingPortal alias. No new backend warnings.
- Frontend `npm.cmd run build`: **passed**, 53 modules transformed.
- Frontend `npm.cmd run lint`: **passed**, zero errors, the same **14 pre-existing
  warnings**; no new warnings in the added integration components.
- Migration applied to guarded test and development databases, both verified at
  **`c7f216a2e485`**. All **45 pre-existing development tables** retained identical
  row counts and original-column data fingerprints. The eight new columns remain
  NULL on all pre-existing rows. No booking/task/ledger history was rewritten.
- An empty downgrade/reapply was verified on the guarded test database, and the
  populated-downgrade refusal was tested in an isolated schema. Disposable test
  schemas were cleaned up. No development downgrade was performed.

New integration tests cover:
optional mappings, draft edits, immutable snapshots/clones, matching services,
origin/context, authorization, provider validation, hourly reservations/capacity,
retry conflicts, actual completion/confirmation/cost/task chain, cancellation and
rebooking, cross-crop protection, current perennial season, planned preparation,
self-work, no fabricated verification/expense, database origin immutability,
concurrent booking/work/expense retries and completion races.

React server rendering checks passed for optional/closed task actions, booking
origin, reused activity/expense forms and application imports. No browser was
available, so interactive and mobile checks below remain manual.

## T. Manual end-to-end checks

1. Restart the backend after migration. As admin, create/clone a **draft** SOP
   version. Assign one task the exact category used by a real verified provider's
   service. Leave an inspection task without a category. Publish.
2. Use a fresh crop plan for this version. Existing published/generated tasks are
   deliberately not retrofitted. Verify mapped task shows Record Work + Book
   Service; unmapped task retains Record Work alone.
3. Choose Book Service. Verify task/due/category and only matching services. Pick
   a real service and available consecutive hourly slots in the existing form.
   Farm/plot/block/crop/task must already be fixed; address remains the normal
   service-address choice. Check empty-category/no-slot messages and Back.
4. Save. Confirm one booking, normal provider notification/reservation behavior,
   and the task still pending. Retry a slow/lost response: no duplicate booking.
5. View Booking. Exercise its existing payment/reschedule/cancel/review controls
   when eligible, and use Open Crop Task to return to the originating Crop Plan.
   Provider booking cards should show the same crop/season/task context read-only.
6. Reject/cancel one booking, then rebook with a different available time. Confirm
   task remains actionable and the cancelled booking stays visible. Try booking
   another genuine service; normal capacity rules must still apply.
7. As provider, Confirm → Start → Complete using the existing time restrictions.
   Do not change clock or bypass those restrictions. As farmer choose Refresh
   service status; verify Service completed and Confirm Work appear.
8. Before confirming, verify no activity/expense or task completion appeared
   automatically. Confirm Work with actual date/type/description and optional
   inputs. Verify one activity in Activities with both task and booking source.
9. Retry work confirmation; one activity only. Correct it through existing activity
   editing if needed. Record Expense, verify suggested booking amount, change to
   actual cost, save and retry; one expense per repeated request. Check crop
   reconciliation uses that actual expense.
10. Choose Complete Task. Confirm existing task status/progress changes while
    officer verification remains unchanged. Repeat Record Work without any
    service to verify the self-performed path remains simple.
11. Repeat on a current perennial season. Close the previous season and confirm
    its tasks cannot start new bookings/confirmed work. A new season's booking,
    activity and expense must appear only in that season. Historical booking
    details must remain readable.
12. Try cross-farmer/task/farm IDs and provider crop writes: reject. Verify a planned
    crop can book and record actual preparation work, but task completion still
    waits for activation under existing rules.
13. Check at 360px, 390px and desktop: task actions, scrolling to the reused forms,
    service matching, fixed context, booking origin links, statuses and errors.
    Ensure no horizontal overflow or accidental repeated form submission.
14. Smoke-test normal marketplace booking without a crop/task, provider availability,
    equipment/service management, payments, reviews, onboarding, harvests/sales,
    season completion and field-officer work.

Stopped at Slice 5. No produce marketplace/delivery, agronomist, livestock, leases,
trees, inventory, weather, AI, subscriptions or new payment architecture added.


## Slice 6 scheduling update

See [CROP_MANAGEMENT_SLICE6.md](CROP_MANAGEMENT_SLICE6.md) for season-start planning, automatic season labels and classified stage/condition/manual tasks. The earlier slice behavior above describes its historical baseline; existing saved plans remain unchanged.
