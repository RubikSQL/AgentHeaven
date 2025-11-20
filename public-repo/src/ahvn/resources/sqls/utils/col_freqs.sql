sqlite:     SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC;
duckdb:     SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC;
postgresql: SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC;
mysql:  SELECT `{col_name}` AS col_enums, COUNT(*) as freq FROM `{tab_name}` GROUP BY `{col_name}` ORDER BY freq DESC;
