select g.games_id, g.year, g.season, g.host_city, g.host_country,
       count(distinct p.athlete_id) as athletes,
       count(distinct case when p.noc_code <> 'UNK' then p.noc_code end) as nocs,
       count(distinct p.sport_id) as sports, count(distinct p.event_id) as events,
       count(distinct case when p.gender = 'F' then p.athlete_id end) as female_athletes,
       count(distinct case when p.gender = 'M' then p.athlete_id end) as male_athletes,
       round(avg(p.age), 2) as mean_age
from {{ source('warehouse', 'games') }} g
left join {{ ref('stg_participations') }} p on p.games_id = g.games_id
where g.year between 1960 and 2026
group by g.games_id, g.year, g.season, g.host_city, g.host_country
