INSTALL spatial; LOAD spatial;

CREATE SCHEMA IF NOT EXISTS gaz;

CREATE OR REPLACE MACRO gaz.canon(s) AS
  TRIM(LOWER(
    REGEXP_REPLACE(
      REGEXP_REPLACE(COALESCE(s,''), '[^[:alnum:][:space:]]', ' '),
      '\\s+', ' '
    )
  ));

-- parameterized helpers (no unbound columns inside the body)
CREATE OR REPLACE MACRO gaz.name_local(n, t) AS
  CASE
    WHEN n IS NOT NULL AND n <> '' THEN n
    WHEN t['name'] IS NOT NULL AND t['name'] <> '' THEN t['name']
    ELSE NULL
END;

CREATE OR REPLACE MACRO gaz.name_en(t) AS NULLIF(t['name:en'], '');