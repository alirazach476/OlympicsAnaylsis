select athlete_id, count(distinct games_id) as games_count, min(year) as first_year, max(year) as last_year,
       sum(case when medal = 'Gold' then 1 else 0 end) as gold, sum(case when medal = 'Silver' then 1 else 0 end) as silver,
       sum(case when medal = 'Bronze' then 1 else 0 end) as bronze, sum(is_medalist) as medals, min(age) as min_age, max(age) as max_age
from {{ ref('stg_participations') }}
group by athlete_id
