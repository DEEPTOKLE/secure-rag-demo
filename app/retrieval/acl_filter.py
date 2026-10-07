"""
ACL predicate builder.

The access-control logic is embedded directly in SQL so that **no**
unauthorised rows can ever reach application code.  Three PostgreSQL
session variables (set per-request in app/db/session.py from the JWT)
drive the predicates:

    app.tenant_id  – integer string; isolates tenant data
    app.user_id    – integer string; exact principal match
    app.user_role  – role string; role-based match

A chunk is visible when the session tenant matches AND the session user
or role is listed in the chunk's `allowed_principals` array.
"""

ACL_PREDICATE = """
    tenant_id = current_setting('app.tenant_id')::int
    AND (
        current_setting('app.user_id') = ANY(allowed_principals)
        OR current_setting('app.user_role') = ANY(allowed_principals)
    )
"""


def get_acl_predicate() -> str:
    """Return the SQL WHERE-clause fragment that enforces the ACL."""
    return ACL_PREDICATE.strip()


def build_search_sql(limit: int = 10) -> str:
    """Assemble the full vector-similarity + ACL query as a single SQL string."""
    return f"""
        SELECT chunk_id,
               raw_text,
               exact_locator,
               source_doc_id,
               source_type,
               embedding <=> CAST(:query_embedding AS vector(384)) AS distance
        FROM chunks
        WHERE {get_acl_predicate()}
        ORDER BY distance
        LIMIT {int(limit)}
    """
