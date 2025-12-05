#!/usr/bin/env python3
import subprocess, tempfile, json, os, sys
API = os.environ.get("API_URL", "http://localhost:8000")
demo_code = "# demo strategy code placeholder\n"

def seed_one(name: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(demo_code.encode("utf-8"))
        f.flush()
        cmd = ["curl","-sS","-X","POST", f"{API}/register_strategy",
               "-F", f"name={name}",
               "-F", f"meta={json.dumps({'symbol':'AAPL','timeframe':'1d'})}",
               "-F", f"code=@{f.name}"]
        out = subprocess.check_output(cmd)
        print(out.decode("utf-8"))

def main():
    names = ["demo_sma5_a","demo_sma5_b","demo_sma5_c","demo_sma5_d","demo_sma5_e"]
    for n in names:
        seed_one(n)

if __name__ == "__main__":
    sys.exit(main())
