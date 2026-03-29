#!/usr/bin/env bash
# Check hitl_approvals state
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -c \
  "SELECT id, status, trade_id, instrument, side,
          row_hash IS NOT NULL as has_hash,
          LENGTH(row_hash) as hash_len
   FROM hitl_approvals ORDER BY requested_at DESC LIMIT 5;"

echo ""
echo "--- trade_lifecycle ---"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -c \
  "SELECT trade_id, current_state, created_at, updated_at
   FROM trade_lifecycle ORDER BY created_at DESC LIMIT 5;"

echo ""
echo "--- trade_state_transitions ---"
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -c \
  "SELECT trade_id, from_state, to_state, transitioned_at
   FROM trade_state_transitions ORDER BY transitioned_at DESC LIMIT 5;"
