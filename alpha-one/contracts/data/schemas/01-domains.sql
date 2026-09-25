-- Shared domains (applied first). Every schema file uses `ULID`; until this
-- file existed no contracts DDL applied to a fresh database (found while
-- building the workers evaluation consumer, docs/64 §6 step 1).
--
-- ULID: 26-char Crockford base32 (envelope.schema.json#/$defs/ULID).
-- Stored as TEXT so lexical order == time order and the value is the same
-- string the envelope carries; a uuid-typed column would force a codec at
-- every boundary.
CREATE DOMAIN ULID AS TEXT
  CHECK (VALUE ~ '^[0-9A-HJKMNP-TV-Z]{26}$');
