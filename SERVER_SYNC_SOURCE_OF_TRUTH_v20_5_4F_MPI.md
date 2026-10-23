# Server Sync Source of Truth — v20.5.4F MPI

This cleaned package is generated from the uploaded local package `ichiban_schema_repair.zip`, the uploaded `Matrix_Independent_Valuation_Constitution_v1.0.docx`, and the latest v20.5.4F MPI Tarzan/BBC Credo files created in this session.

## Sync rule

This package should be treated as the current local source of truth for the next server synchronization. The server should not retain older/conflicting Tarzan/BBC credo files or generated runtime artifacts that do not match this package.

## Cleanup applied before server sync

- Removed Python cache directories and compiled `.pyc` files.
- Removed generated runtime valuation outputs under `data/`, preserving only `data/.gitkeep`.
- Replaced superseded v20.5.4/v20.5.4E credo files with the latest v20.5.4F MPI Tarzan and BBC files.
- Added the Matrix Independent Valuation Constitution as a project governance/control-review document.
- Preserved source code, parser modules, Streamlit pages, reporting modules, governance files, docs, and requirements.

## Scope boundary

This sync does not intentionally rewrite valuation math. It promotes the current local program state and updated governance/credo files. Tarzan remains the current active repair focus; BBC remains future/reference unless explicitly activated.
