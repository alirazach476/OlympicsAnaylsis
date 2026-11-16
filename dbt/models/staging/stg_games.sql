-- Phase 3: replace with source() once dbt sources are wired to Postgres.
select
  games_id,
  year,
  season,
  official_edition_name,
  host_city,
  host_country,
  verification_status
from games
