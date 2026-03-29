#!/usr/bin/env bash
docker exec aa_local_db psql -U app_trading -d autonomous_alpha -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
