sqlite:     SELECT name AS col_name FROM pragma_table_info('{tab_name}');
duckdb:     SELECT column_name AS col_name FROM information_schema.columns WHERE table_name = '{tab_name}' AND table_schema = 'main';
postgresql: SELECT column_name AS col_name FROM information_schema.columns WHERE table_name = '{tab_name}';
mysql:      SELECT COLUMN_NAME AS col_name FROM information_schema.COLUMNS WHERE TABLE_NAME = '{tab_name}';
