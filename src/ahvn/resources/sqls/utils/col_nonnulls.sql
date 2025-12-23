sqlite:     SELECT "{col_name}" AS col_enums FROM "{tab_name}" WHERE "{col_name}" IS NOT NULL;
duckdb:     SELECT "{col_name}" AS col_enums FROM "{tab_name}" WHERE "{col_name}" IS NOT NULL;
postgresql: SELECT "{col_name}" AS col_enums FROM "{tab_name}" WHERE "{col_name}" IS NOT NULL;
mysql:      SELECT `{col_name}` AS col_enums FROM `{tab_name}` WHERE `{col_name}` IS NOT NULL;
mssql:      SELECT [{col_name}] AS col_enums FROM [{tab_name}] WHERE [{col_name}] IS NOT NULL;