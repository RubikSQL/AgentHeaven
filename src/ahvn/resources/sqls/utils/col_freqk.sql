sqlite:     SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC LIMIT {topk};
duckdb:     SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC LIMIT {topk};
postgresql: SELECT "{col_name}" AS col_enums, COUNT(*) as freq FROM "{tab_name}" GROUP BY "{col_name}" ORDER BY freq DESC LIMIT {topk};
mysql:      SELECT `{col_name}` AS col_enums, COUNT(*) as freq FROM `{tab_name}` GROUP BY `{col_name}` ORDER BY freq DESC LIMIT {topk};
mssql:      SELECT [{col_name}] AS col_enums, COUNT(*) as freq FROM [{tab_name}] GROUP BY [{col_name}] ORDER BY freq DESC OFFSET 0 ROWS FETCH NEXT {topk} ROWS ONLY;