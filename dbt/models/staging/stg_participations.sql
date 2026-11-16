-- Silver: de-duplicated participations with standardised NOC (alias map) and a medalist flag.
select
    p.participation_id, p.athlete_id, p.games_id, g.year, g.season, p.sport_id, s.sport_name, p.event_id,
    coalesce(al.standard_code, nullif(p.noc_code, ''), 'UNK') as noc_code,
    case when a.gender in ('M','Men','Male') then 'M' when a.gender in ('F','Women','Female') then 'F' end as gender,
    p.age_at_competition as age,
    case when p.medal in ('Gold','Silver','Bronze') then p.medal end as medal,
    case when p.medal in ('Gold','Silver','Bronze') then 1 else 0 end as is_medalist
from (select * from {{ source('warehouse', 'athlete_participations') }} group by athlete_id, games_id, event_id) p
join {{ source('warehouse', 'games') }} g on g.games_id = p.games_id
left join {{ source('warehouse', 'sports') }} s on s.sport_id = p.sport_id
left join {{ source('warehouse', 'athletes') }} a on a.athlete_id = p.athlete_id
left join {{ source('warehouse', 'ref_noc_alias') }} al on al.games_id = p.games_id and al.source = 'athletes' and al.source_code = p.noc_code
where g.year between 1960 and 2026
