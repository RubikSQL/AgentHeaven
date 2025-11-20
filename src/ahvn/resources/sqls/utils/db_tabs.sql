sqlite:     SELECT name AS tab_name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';
duckdb:     SELECT table_name AS tab_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE';
postgresql: SELECT tablename AS tab_name FROM pg_tables WHERE schemaname='public';
mysql:      SELECT TABLE_NAME AS tab_name FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE();