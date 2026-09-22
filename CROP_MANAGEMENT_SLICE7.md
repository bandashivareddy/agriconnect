# Slice 7 — Shared signup and Field Officer applications

## Baseline reconciliation

The missing `users.signup_intent` column came from partial Slice 7 work in the
current working tree. The auth SELECTs and new migration already existed, but
only the guarded test database had received that migration. The development
database was still at the completed Slice 6 head `d8a327b3f596`.

The correction uses the explicit next migration **`e9b438c4a607`**, whose parent
is **`d8a327b3f596`**. It was first validated on the guarded test database,
including downgrade/reapply and data comparison, then applied to development
with the same original-column fingerprint method as Slice 6. No manual ALTER,
baseline reset, historical backfill, or completed Slice 6 rollback was used.
Both database schemas now support the auth code's `signup_intent` SELECTs.

## Architecture and signup behavior

One shared `/auth/register`, `/auth/login`, `/auth/me`, JWT and users system
remains. `user_capabilities` and its existing effective-capability resolver
remain the source of workspace access. No separate officer login or permissions
framework was introduced.

| Signup code | UI label | Persisted legacy role | Initial access |
| --- | --- | --- | --- |
| `farmer` | Farmer | `farmer` | Existing farmer onboarding |
| `provider` | Service Provider | `supplier` | Existing profile/service onboarding |
| `field_officer` | Field Officer, Application required | `member` | Pending application only |
| `landowner` | Landowner | `member` | Managed farming coming later placeholder |

`member` is a neutral value added to the existing legacy role constraint. It
grants no fallback capability. This is necessary because the old non-null role
column required farmer, supplier or admin, all of which confer access. It is not
another role column or a Field Officer permission. Historical roles and explicit
capabilities remain untouched.

`signup_intent` is nullable informational context, not authorization. Existing
clients using `user_role=farmer/supplier` still work and keep a NULL intent.
New signup sends a stable `signup_intent`. Conflicting legacy role/intent pairs,
admin/agronomist intent, and privileged nested application fields are rejected.

Mobile-first role cards come from `/auth/signup-options`. UI labels/descriptions
are separate from stable codes. Mobile-number login remains first-class, email
optional, and shared account contact fields are reused. Supplier database/API
names stay unchanged; signup and affected user-visible wording say Service Provider.

Farmer farm/address setup, interrupted onboarding, provider profile plus first
service, and Become a Provider remain on their existing paths. Applying for
officer access does not create a second farmer/provider user.

## Schema

Migration `backend/alembic/versions/e9b438c4a607_officer_applications.py`:

- Extend `users_user_role_check` with neutral `member`.
- Add nullable `users.signup_intent varchar(20)` constrained to the four codes.
  No defaults or historical values are fabricated.
- Add `field_officer_applications`:
  - identity `application_id` primary key;
  - unique `user_id`, FK to existing users, delete restricted;
  - status `pending`, `approved`, `rejected`, default pending;
  - optional qualification (300), experience_years numeric(4,1), constrained 0–80;
  - optional crops_or_domains_known (1000), operating_area_text (500),
    languages_known (300), notes (2000);
  - created_at / updated_at timestamptz;
  - nullable reviewed_at, reviewed_by FK, rejection_reason (2000).
- Queue index `(status, created_at, application_id)`; unique user supports
  one submitted application and duplicate-submit protection.
- Constraints pair review data with terminal status, require a nonblank rejection
  reason, reject a reason on approval and prevent self-review.
- Triggers protect submitted content/review history, validate independent admin
  review, atomically grant approved access, and block pending/rejected applicants
  from receiving officer access through a legacy capability insert.

Names, mobile numbers and email are not copied into applications. Read endpoints
join the current account details and reviewer name. No credentials, attachments,
officer profile, geography, managed-farming entity or Landowner capability added.

Downgrade refuses if any application, signup intent, or neutral account exists;
it cannot silently discard signup/review history. An empty downgrade is supported.

## Application lifecycle and review

New Field Officer signup collects optional application details alongside the
existing account fields. **Create account and submit application** saves the user
and pending application in one transaction, then uses the normal login. A failure
rolls both back. Nothing grants `field_officer` on signup.

Existing farmer/provider users can choose **Apply as Field Officer** from the
marketplace header. This submits an application for the same authenticated user.
Known name/contact details are reused; another user ID is not accepted in the
payload. Existing officers cannot create a redundant application.

Pending users see “Your Field Officer application is under review.” Signing out
and back in preserves the pending state. Rejected users see the reason, can still
sign in, and do not receive officer access. Neither state blocks an existing
farmer/provider user's independently authorized workspace.

Admin → Field Officer Applications provides pending, approved and rejected
queues, detail, review time/reviewer and reason. Decisions are:

- pending → approved;
- pending → rejected, with a required reason shown to the applicant.

Submission fields and terminal decisions are immutable. No resubmission,
withdrawal, re-review, or credential-verification workflow is implemented.

Reviews lock the applicant's user row and application row, using the same
user-first ordering as submissions and legacy grants. Approval updates the review
and its database trigger inserts `(user_id, 'field_officer')` using the existing
`ON CONFLICT DO NOTHING` pattern in the same transaction. No duplicate capability
is possible. Identical approval/rejection retries return the original decision
and audit; conflicting decisions return 409. Repeating approval does not reverse
a later intentional capability removal.

Application submission is also retry-safe: the same user's identical details
return the saved application (200 after initial 201); changed details conflict.
Normal account registration retains the existing duplicate-contact handling.
After a lost signup response, the user can sign in to the saved account rather
than create another account.

## APIs and authorization

| Method / API | Access and behavior |
| --- | --- |
| GET `/auth/signup-options` | Public stable codes plus UI labels/descriptions/notices |
| POST `/auth/register` | Existing shared signup; optional signup_intent and field_officer_application; legacy farmer/supplier request supported |
| POST `/auth/login`, GET `/auth/me` | Existing auth; returns saved signup_intent alongside capabilities |
| GET `/my/field-officer-application` | Authenticated user's application/contact/review, or null |
| POST `/my/field-officer-application` | Authenticated user's first application; actor from auth; identical retry supported |
| GET `/admin/field-officer-applications` | Effective admin; status filter (default pending), limit 1–100 (default 30), offset |
| GET `/admin/field-officer-applications/{id}` | Effective admin detail |
| POST `/admin/field-officer-applications/{id}/review` | Effective admin except applicant; approved/rejected + rejection_reason |
| POST `/admin/field-officers` | Existing staff grant retained; pending/rejected applicants must use application review instead |

No applicant edit-by-ID route or review self-service route exists. Non-admin
review/list/detail calls fail authorization; extra identity/review fields in
application input are rejected. Even an admin cannot review their own application.

Approval adds no assignments and no farm/crop permissions. The unchanged Slice 2A
routes still require officer capability plus explicit active assignment for crop,
visit and observation access. Approved but unassigned users can open My Field
Work and see an empty assignment list, but arbitrary crop reads return 404.
Closing an assignment removes its access under existing rules.

The existing shared auth checks are retained, including rejecting unknown/deleted
accounts or invalid tokens. The existing users model has no general account
deactivation flag; this slice does not invent one or alter provider active status.

## Multi-workspace and Landowner behavior

Farmer/provider roles and capabilities are never replaced on application or
approval. Farmer + provider + officer is supported on the same user. Existing
workspace routing remains; Field Officer work can be accessed independently of
optional farmer/provider setup, while those workflows retain their own setup
requirements.

An approved applicant can sign in again or use **Open My Field Work**, which
refreshes `/auth/me` before navigation. Merely changing local page state cannot
bypass server authorization. No large workspace-switcher redesign.

Landowner creates a neutral shared account with informational signup intent and
a “Managed farming coming later” screen. It grants no farming, officer, or
managed-farming authority. No assessment, contract, investment, ROI or operational
workflow exists. No Agronomist signup option is exposed.

## Files changed

Backend:

- `backend/officer_applications.py` — new request models, signup option constants,
  transactional submission helper and application/review router.
- `backend/main.py` — small additive shared signup/auth fields and router hookup.
- `backend/field_work.py` — legacy grant directs applicants to review.
- `backend/alembic/versions/e9b438c4a607_officer_applications.py` — new migration.
- `backend/scripts/verify_slice7_migration.py` — guarded Slice 6-style verifier.
- `backend/tests/test_officer_applications.py` — new behavior/security tests.
- `backend/tests/test_officer_application_concurrency.py` — new isolated races.

Frontend:

- `frontend/src/AuthPage.jsx`, `AuthPage.css` — selectable role cards and optional
  application fields; shared login unchanged.
- `frontend/src/OfficerApplications.jsx` — reusable application fields, applicant
  status, admin queue/detail/review.
- `frontend/src/App.jsx` — applicant/placeholder/admin navigation and account
  refresh after approval; existing onboarding retained.
- `frontend/src/AdminDashboard.jsx` — applications entry and terminology.
- `frontend/src/FieldWorkAdmin.jsx` — review guidance and access terminology.
- `frontend/src/BookingForm.jsx` — Service Provider wording only.

Documentation: this report, README and a forward note in the Slice 2A report.
No previous migrations, baseline SQL or existing test assertions were changed.

## Validation

- Complete backend suite: **378 passed** in 86.36 seconds — all **348 baseline
  tests** plus **30 new tests** (25 behavior/security tests, 5 concurrency/migration
  tests). Existing marketplace, provider/onboarding, Crop Management and Field
  Officer assignment tests remain green.
- Command from `backend`: `..\.venv\Scripts\python.exe -m pytest tests -q`.
- Two existing dependency warnings only: Starlette/httpx TestClient deprecation
  and AnyIO BlockingPortal alias deprecation.
- Frontend `npm.cmd run build`: **passed**, 54 modules, JS 448.93 kB / gzip
  116.63 kB. `npm.cmd run lint`: **passed**, zero errors and the same **14 existing
  warnings**, none added by the new application/signup components.
- Initial rollback tests were corrected to assert the existing middleware's HTTP
  500 response rather than expecting a propagated exception. The rollback/data
  assertions pass; no production error handling was changed to accommodate tests.
- Interactive browser/mobile testing was not performed; use the steps below.

New tests cover stable options; all four signup intentions and mobile login;
neutral/pending access; contact reuse; queue/detail; approval/rejection/reasons;
exactly-one capability and review replay; independent admin/self-review security;
cross-user mutation denial; immutable history; legacy-grant bypass prevention;
existing officer/account preservation; invalid privileged signup fields;
transaction rollback; assigned/unassigned access; multi-workspace and Become a
Provider; concurrent approval, conflicting decisions, duplicate submission,
submission-vs-grant, and populated-downgrade refusal.

Data preservation: test and development both migrated to `e9b438c4a607` through
the guarded helper. All **45 pre-existing tables** retained identical row counts
and complete original-column fingerprints, excluding only Alembic tracking.
Historical signup_intent values remained NULL; the new application table was
empty immediately after migration. The guarded test downgrade/reapply passed.
No development downgrade or ad-hoc data patch was performed.

## Exact manual browser tests

Restart the backend and reload the frontend after migration.

1. **Pending signup:** Sign out → Create account → select Field Officer. Confirm
   “Application required”, enter name, mobile and password (leave email empty),
   optionally enter qualification/experience/area/languages, then **Create account
   and submit application**. Verify the under-review screen, saved contact data,
   and no My Field Work access. Sign out/sign in by mobile: still pending.
2. **Approve:** Sign in as a different admin → **Field Officer Applications** →
   Pending → Review application → Approve → Confirm decision. Verify reviewer/time,
   approved status and Manage Field Work / Assign a crop action. Refresh/retry:
   original decision remains. Applicant signs in again (or refreshes status and
   opens My Field Work): workspace opens with no assignments or arbitrary farms.
3. **Assignment boundary:** Admin → Manage Field Work → assign exactly one crop
   to that officer and schedule a visit. Officer can open that assigned crop/visit.
   An unrelated crop's `/field-work/crop-cycles/{id}` must return 404. Close the
   assignment; the officer loses that scope but keeps their account/workspace.
4. **Reject:** Create a second Field Officer account. Admin rejects with a reason.
   Applicant signs back in and sees that reason, without officer access. Check
   the admin Rejected filter retains the application. The older Enable Field
   Officer action must reject attempts to bypass this review.
5. **Existing accounts:** Create a Farmer account and complete the existing first
   farm/address setup; interrupt and resume once. Choose Become a Provider, save
   provider details and add the first service; confirm same account, Provider
   Dashboard and normal service/availability/booking flow. Separately create a
   Service Provider signup and confirm its existing first-service setup gate.
6. **Multiple workspaces:** On a farmer/provider account choose Apply as Field
   Officer. While pending/rejected, existing farm/provider tools still work. After
   approval, My Field Work is added without duplicating or replacing that account.
7. **Landowner/mobile:** Create a Landowner account; sign out/in and verify only
   the coming-later state, with no managed-farming workflow. At 360px/390px and
   desktop check cards, long application text, labels, keyboard selection, review
   errors/retries and navigation. Browser/mobile interactive checks remain manual.

## Deferred items

No resubmission, review reversal, withdrawal, credential verification, officer
attachments, general account deactivation, separate logins, or major workspace UX.
Legacy admin-granted staff without an application retain their prior workflow;
new applicants cannot use that path to bypass review.

No localization/Telugu framework, WhatsApp, GPS/LGD/geography, reporting, master
import/export, Super Admin, managed farming, agronomist work, weather, produce
marketplace, livestock, tree tracking, payments or provider verification redesign.
Stopped after Slice 7.
