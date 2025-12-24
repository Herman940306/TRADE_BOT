# Guardian Unlock – Secure Operations Guide

## Purpose

The **Guardian Service** enforces hard safety locks (e.g. daily loss limits) to protect capital.
When a lock is triggered, trading is intentionally blocked until an explicit, auditable unlock action is taken.

This document defines:
- ✅ The **one‑shot CLI unlock command** (recommended default)
- ✅ An **authenticated API unlock contract** (optional, advanced)
- ✅ Operational safeguards and audit guarantees
- ✅ How this is presented to users (RUNBOOK / README guidance)

---

## Design Principles

1. **Safety First**
   - Unlocking must be deliberate, explicit, and traceable
   - No silent auto‑unlocking in production

2. **Auditability**
   - Every unlock has a reason, operator, timestamp, and correlation ID
   - All unlocks are logged and persisted

3. **User‑Friendly**
   - One clear command
   - Human‑readable output
   - No manual file deletion required

4. **Composable**
   - Works without running an API server
   - API option available for advanced deployments

---

## Recommended Default: One‑Shot CLI Unlock

### Why This Is Best Practice

For most users (and customers), **CLI unlock is the safest and most intuitive option**:

- No HTTP server exposure
- Works inside Docker / bare metal
- Easy to document and support
- Matches industry patterns (e.g. `vault operator unseal`, `kubectl drain`)

---

## CLI Command Specification

### Command

```bash
python -m tools.guardian unlock \
  --reason "Manual reset after verified issue" \
  --operator "Halo" \
  --confirm
