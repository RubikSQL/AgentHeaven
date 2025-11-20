sqlite:     SELECT name AS col_name FROM pragma_table_info('{tab_name}') WHERE pk > 0;
duckdb:     SELECT name AS col_name FROM pragma_table_info('{tab_name}') WHERE pk > 0;
postgresql: SELECT column_name AS col_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name WHERE tc.table_name = '{tab_name}' AND tc.constraint_type = 'PRIMARY KEY';
mysql:      SELECT COLUMN_NAME AS col_name FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_NAME = '{tab_name}' AND CONSTRAINT_NAME = 'PRIMARY';
