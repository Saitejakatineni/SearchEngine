"""
Creates the 'nutch' Solr core and configures the schema fields
that app.py expects: url, title, content, digest, boost, tstamp.

Run once, before crawl_and_index.py.
Usage:
    python3 setup_solr.py
"""
import glob
import os
import shutil
import subprocess
import sys

import requests

SOLR     = "http://localhost:8983/solr"
CORE     = "nutch"
SOLR_BIN = "/usr/local/Cellar/solr/10.0.0/bin/solr"
DATA_DIR = "/usr/local/var/lib/solr"
CONFIGSETS_SRC = "/usr/local/Cellar/solr/10.0.0/server/solr/configsets/_default/conf"


def find_solr_bin():
    """Return the solr binary path, searching common Homebrew locations."""
    candidates = [
        SOLR_BIN,
        "/opt/homebrew/Cellar/solr/10.0.0/bin/solr",  # Apple Silicon
    ] + glob.glob("/usr/local/Cellar/solr/*/bin/solr") \
      + glob.glob("/opt/homebrew/Cellar/solr/*/bin/solr")

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def find_configsets_src():
    """Return the _default configset conf dir from the Solr installation."""
    candidates = glob.glob("/usr/local/Cellar/solr/*/server/solr/configsets/_default/conf") \
               + glob.glob("/opt/homebrew/Cellar/solr/*/server/solr/configsets/_default/conf")
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def solr_post(path, **kwargs):
    url = f"{SOLR}/{path}"
    resp = requests.post(url, **kwargs)
    resp.raise_for_status()
    return resp.json()


def core_exists():
    resp = requests.get(f"{SOLR}/admin/cores", params={"action": "STATUS", "core": CORE})
    status = resp.json().get("status", {})
    return bool(status.get(CORE))


def create_core(solr_bin, configsets_src):
    core_conf_dst = os.path.join(DATA_DIR, CORE, "conf")

    # Copy the _default configset into the core directory so Solr can find it
    if not os.path.isdir(core_conf_dst):
        os.makedirs(core_conf_dst, exist_ok=True)
        shutil.copytree(configsets_src, core_conf_dst, dirs_exist_ok=True)
        print(f"  Copied configset → {core_conf_dst}")

    result = subprocess.run(
        [solr_bin, "create", "-c", CORE],
        capture_output=True, text=True
    )
    if "Created new core" in result.stdout:
        print(f"  Core '{CORE}' created.")
    elif core_exists():
        print(f"  Core '{CORE}' is up.")
    else:
        print(result.stdout)
        print(result.stderr)
        sys.exit(f"Failed to create core '{CORE}'.")


def add_field(name, field_type, stored=True, indexed=True):
    """Add a field via the Schema API, skip if it already exists."""
    try:
        solr_post(f"{CORE}/schema", json={
            "add-field": {
                "name":     name,
                "type":     field_type,
                "stored":   stored,
                "indexed":  indexed,
            }
        })
        print(f"  Field '{name}' ({field_type}) added.")
    except requests.HTTPError as e:
        if "already exists" in e.response.text:
            print(f"  Field '{name}' already exists, skipping.")
        else:
            raise


def main():
    # Verify Solr is running
    try:
        requests.get(f"{SOLR}/admin/info/system", timeout=5)
    except requests.ConnectionError:
        sys.exit("Solr is not running. Start it with:  brew services start solr")

    solr_bin      = find_solr_bin()
    configsets_src = find_configsets_src()

    if not solr_bin:
        sys.exit("Could not find the solr binary. Is Solr installed?  brew install solr")
    if not configsets_src:
        sys.exit("Could not find Solr's _default configset. Check your Solr installation.")

    print(f"\n1. Checking core '{CORE}' …")
    if core_exists():
        print(f"   Core '{CORE}' already exists, skipping creation.")
    else:
        print(f"   Core '{CORE}' not found — creating …")
        create_core(solr_bin, configsets_src)

    print("\n2. Configuring schema fields …")
    add_field("url",     "string")
    add_field("title",   "text_general")
    add_field("content", "text_general")
    add_field("digest",  "string")
    add_field("boost",   "pfloat",  indexed=False)
    add_field("tstamp",  "pdate",   indexed=False)

    print(f"\nDone. Core '{CORE}' is ready.")
    print("Next step:  python3 crawl_and_index.py")


if __name__ == "__main__":
    main()
