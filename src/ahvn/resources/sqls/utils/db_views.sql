sqlite:     SELECT name AS view_name FROM sqlite_master WHERE type='view';
duckdb:     SELECT table_name AS view_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'VIEW';
postgresql: SELECT viewname AS view_name FROM pg_views WHERE schemaname='public';
mysql:      SELECT TABLE_NAME AS view_name FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'VIEW';
