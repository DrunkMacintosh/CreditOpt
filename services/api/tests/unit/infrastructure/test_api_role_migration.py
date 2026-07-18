from pathlib import Path


def test_api_role_migration_is_nologin_nobypassrls_and_actor_scoped() -> None:
    workspace = Path(__file__).resolve().parents[5]
    migration = workspace / "supabase/migrations/202607170009_api_role_rls.sql"

    assert migration.exists()
    sql = migration.read_text().lower()
    assert "alter role creditops_api nologin nobypassrls" in sql
    assert "grant creditops_api to service_role" in sql
    assert "password" not in sql
    assert sql.count("to creditops_api") >= 8
    assert "auth.uid()" in sql
    assert "revoked_at is null" in sql
    case_select_policy = sql.split("create policy credit_cases_api_select", 1)[1].split(
        "create policy credit_cases_api_insert", 1
    )[0]
    assert "created_by" not in case_select_policy
    assert "security definer" in sql
    assert "set search_path = pg_catalog" in sql
    assert "api_actor_created_case(case_assignments.case_id" in sql
