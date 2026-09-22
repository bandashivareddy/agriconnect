# Backend regression tests

Run from `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest
```

Tests require `AGRI_TEST_DB_NAME` in `backend/.env`. They refuse to start unless it is non-empty, differs from `DB_NAME`, contains `test`, and the connected database reports that exact name. Test records use the `@pytest.agriconnect.test` email domain and are deleted after each test.

`agriconnect_test` was initialized once with PostgreSQL schema-only dump/restore tooling after checking `current_database()` against `AGRI_TEST_DB_NAME`. Never run schema copy, cleanup, or test commands against `DB_NAME`, and never copy development data into the test database.
