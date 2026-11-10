import os

import bpy
from pathlib import Path
import shutil
import tomllib
import bl_pkg

root = Path(os.environ["BLENDER_USER_RESOURCES"])
remote = root / "feed"
shutil.copytree(os.environ["MW_FEED_BASELINE"], remote)
installed = root / "installed"
identifier = "mw_cs2_batch_exporter"
prefs = bpy.context.preferences
prefs.system.use_online_access = True
assert bpy.app.online_access
repos = prefs.extensions.repos
repo = repos.new(name="MW Local Release Test", module="mw_release_test", custom_directory=str(installed), remote_url=(remote / "index.json").as_uri())
repo.use_custom_directory = True
repo.use_remote_url = True

def sync():
    assert bpy.ops.extensions.repo_sync(repo_directory=str(installed)) == {"FINISHED"}

def install(expected):
    assert bpy.ops.extensions.package_install(repo_directory=str(installed), pkg_id=identifier, enable_on_install=True) == {"FINISHED"}
    with (installed / identifier / "blender_manifest.toml").open("rb") as handle:
        assert tomllib.load(handle)["version"] == expected
    assert f"bl_ext.{repo.module}.{identifier}" in prefs.addons

def outdated():
    return bl_pkg.repo_stats_calc_outdated_for_repo_directory(bl_pkg.repo_cache_store_ensure(), str(installed))

assert not installed.exists()
sync()
install("0.1.25")
assert outdated() == 0
# Only serve the index and packages; the candidate may be a Git checkout.
candidate = Path(os.environ["MW_FEED_CANDIDATE"])
for path in candidate.glob("*.zip"):
    shutil.copy2(path, remote)
shutil.copy2(candidate / "index.json", remote)
sync()
assert outdated() == 1
install("0.1.26")
assert outdated() == 0
print("MW_FEED_SMOKE_OK")
