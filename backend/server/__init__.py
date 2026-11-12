"""AutoApply local backend: serves frontend/docs/api.md under /api for the single local user.

Run it from backend/ with `python -m server`. Use one server process per data directory; the
JSON store is guarded by an in-process lock only.
"""
