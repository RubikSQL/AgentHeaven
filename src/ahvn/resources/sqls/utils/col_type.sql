sqlite:     SELECT type AS col_type FROM pragma_table_info('{tab_name}') WHERE name = '{col_name}';
duckdb:     SELECT data_type AS col_type FROM information_schema.columns WHERE table_name = '{tab_name}' AND column_name = '{col_name}';
postgresql: SELECT data_type AS col_type FROM information_schema.columns WHERE table_name = '{tab_name}' AND column_name = '{col_name}';
mysql:      SELECT DATA_TYPE AS col_type FROM information_schema.COLUMNS WHERE TABLE_NAME = '{tab_name}' AND COLUMN_NAME = '{col_name}';
