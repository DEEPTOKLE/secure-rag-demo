-- 003_rls_policies.sql
-- Row Level Security: a SECOND enforcement layer.
-- Even if an application query forgets the explicit WHERE clause in
-- vector_search.py, these policies still prevent unauthorized reads.
--
-- The per-request SET LOCAL (in app/db/session.py) populates the
-- app.* GUC variables from the decoded JWT.
--   app.tenant_id  – organisation scope
--   app.user_id    – the authenticated user's integer id (as text)
--   app.user_role  – the authenticated user's role string

-- Enable RLS on both tables
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_records ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- chunks policy
-- ---------------------------------------------------------------------------
-- A row is visible when the session user belongs to the same tenant AND
-- is listed explicitly by user-id or implicitly by role.
CREATE POLICY chunks_tenant_isolation ON chunks
    USING (
        tenant_id = current_setting('app.tenant_id')::int
    );

CREATE POLICY chunks_principal_access ON chunks
    USING (
        current_setting('app.user_id') = ANY(allowed_principals)
        OR current_setting('app.user_role') = ANY(allowed_principals)
    );

-- ---------------------------------------------------------------------------
-- employee_records policy
-- ---------------------------------------------------------------------------
CREATE POLICY employee_records_tenant_isolation ON employee_records
    USING (
        tenant_id = current_setting('app.tenant_id')::int
    );

CREATE POLICY employee_records_principal_access ON employee_records
    USING (
        current_setting('app.user_id') = ANY(allowed_principals)
        OR current_setting('app.user_role') = ANY(allowed_principals)
    );
