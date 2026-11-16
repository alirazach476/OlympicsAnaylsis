select games_id, noc_code,
       sum(case when medal_type = 'Gold' then 1 else 0 end)   as gold,
       sum(case when medal_type = 'Silver' then 1 else 0 end) as silver,
       sum(case when medal_type = 'Bronze' then 1 else 0 end) as bronze,
       count(*) as total
from {{ ref('stg_medal_awards') }}
group by games_id, noc_code
