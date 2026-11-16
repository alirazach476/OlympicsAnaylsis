-- singular test: returns rows only when a country total differs from gold+silver+bronze
select * from {{ ref('mart_country_medals') }} where total <> gold + silver + bronze
