"""Native PostgreSQL 16 row-level security for TPC-DS and BIRD (E5P on all four domains): loads the original and the
perturbed instances into the embedded server of native_rls.py with the same row policies and column grants."""
import sys

from domains import DOMAINS
from enforce import pg_uri
import native_rls

if __name__ == "__main__":
    admin = pg_uri()
    for name in (sys.argv[1:] or ["bird", "tpcds"]):
        d = DOMAINS[name]()
        native_rls.load(admin, d, f"{d.name}_orig", d.db, "main", list(d.P))
        for p in d.P:
            native_rls.load(admin, d, f"{d.name}_pert_{p}", d.pert, f"pert_{p}", [p])
        print("loaded", name, flush=True)
