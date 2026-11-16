-- Gold: country medal performance per edition. Ties share a rank (RANK over gold, silver, bronze).
select m.games_id, g.year, g.season, m.noc_code, coalesce(h.historical_name, m.noc_code) as country_name,
       m.gold, m.silver, m.bronze, m.total,
       rank() over (partition by m.games_id order by m.gold desc, m.silver desc, m.bronze desc) as official_rank,
       round(1.0 * m.gold / nullif(m.total, 0), 4) as gold_ratio,
       round(1.0 * m.total / sum(m.total) over (partition by m.games_id), 4) as medal_share,
       case when m.noc_code = hn.host_noc then 1 else 0 end as is_host
from {{ ref('int_country_edition_medals') }} m
join {{ source('warehouse', 'games') }} g on g.games_id = m.games_id
left join {{ source('warehouse', 'historical_nocs') }} h on h.noc_code = m.noc_code
left join {{ source('warehouse', 'ref_host_noc') }} hn on hn.games_id = m.games_id
