from sqlalchemy import create_engine, text

e = create_engine("sqlite+pysqlite:///./data/olympics_warehouse.db")
with e.connect() as c:
    print("matches", c.execute(text("select count(*) from matches")).scalar())
    print("by_games", list(c.execute(text("select games_id,count(*) c from matches group by 1 order by 1"))))
    print(
        "sample_37280",
        list(
            c.execute(
                text(
                    "select home_score, away_score, source_url from matches "
                    "where source_url like :p"
                ),
                {"p": "%37280%"},
            )
        ),
    )
