"""Convert BIRD dev `financial.sqlite` into data/bird_financial.duckdb.
Usage: python scripts/prepare_bird.py /path/to/dev_databases/financial/financial.sqlite"""
import os, sys
import duckdb
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bird_financial.duckdb")
con = duckdb.connect(out)
con.execute("INSTALL sqlite; LOAD sqlite")
con.execute(f"ATTACH '{sys.argv[1]}' AS sq (TYPE sqlite, READ_ONLY)")
for t in ("account", "card", "client", "disp", "district", "loan", "order", "trans"):
    try:
        con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM sq."{t}"')
    except Exception as e:
        print("skip", t, e)
print("wrote", out)
