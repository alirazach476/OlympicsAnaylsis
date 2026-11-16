select * from {{ ref('mart_country_medals') }} where noc_code like 'X\_%' escape '\' or country_name glob '[0-9]*'
