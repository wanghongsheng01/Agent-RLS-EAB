"""Build every benchmark database and its perturbed twin (TPC-H SF0.05, TPC-DS SF1 via DuckDB extensions; enterprise
policy model from a fixed seed; BIRD financial from data/bird_financial.duckdb)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code"))
import duckdb
from domains import DOMAINS, PILOT
import enforce
os.makedirs(PILOT, exist_ok=True)
if not os.path.exists(os.path.join(PILOT, "tpch.duckdb")):
    c = duckdb.connect(os.path.join(PILOT, "tpch.duckdb")); c.execute("INSTALL tpch; LOAD tpch; CALL dbgen(sf=0.05)"); c.close()
if not os.path.exists(os.path.join(PILOT, "tpcds.duckdb")):
    c = duckdb.connect(os.path.join(PILOT, "tpcds.duckdb")); c.execute("INSTALL tpcds; LOAD tpcds; CALL dsdgen(sf=1)"); c.close()
for k, D in DOMAINS.items():
    d = D(); d.build_pert(); enforce.build_e5(d); print("built", k)
