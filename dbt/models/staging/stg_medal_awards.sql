-- Silver: ONE row per event result x NOC x medal (team medals counted once). Olympedia podiums are the authority for medal totals.
select distinct
    p.games_id, p.result_id, p.sport_name, p.event_name,
    coalesce(al.standard_code, p.noc) as noc_code, p.medal as medal_type
from {{ source('warehouse', 'olympedia_podium_results') }} p
join {{ source('warehouse', 'games') }} g on g.games_id = p.games_id
left join {{ source('warehouse', 'ref_noc_alias') }} al on al.games_id = p.games_id and al.source = 'athletes' and al.source_code = p.noc
where p.medal in ('Gold','Silver','Bronze') and p.noc is not null and p.noc <> '' and g.year between 1960 and 2026
