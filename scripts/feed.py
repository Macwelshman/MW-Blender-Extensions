#!/usr/bin/env python3
"""Validate the MW extension feed, audit GitHub, or stage one source release."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ARCHIVE_KEYS = {"archive_url", "archive_size", "archive_hash"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version(value):
    require(isinstance(value, str) and re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value),
            f"invalid version: {value!r}")
    return tuple(map(int, value.split(".")))


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def manifest(path):
    with zipfile.ZipFile(path) as archive:
        require(archive.namelist().count("blender_manifest.toml") == 1, "expected one root manifest")
        require(archive.namelist().count("__init__.py") == 1, "expected one root __init__.py")
        require(archive.testzip() is None, "ZIP member CRC failed")
        init = ast.parse(archive.read("__init__.py"), filename="__init__.py")
        data = tomllib.loads(archive.read("blender_manifest.toml").decode())
    for key in ("id", "name", "tagline", "maintainer", "type", "version", "blender_version_min"):
        require(isinstance(data.get(key), str) and data[key].strip(), f"invalid or missing {key}")
    require(re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", data["id"]), "invalid extension ID")
    require(data.get("schema_version") == "1.0.0" and data["type"] == "add-on",
            "unsupported manifest schema or extension type")
    require(isinstance(data.get("license"), list) and data["license"]
            and all(isinstance(item, str) and item.startswith("SPDX:") and item[5:].strip()
                    for item in data["license"]), "invalid license")
    version(data["version"])
    minimum = version(data["blender_version_min"])
    require(minimum >= (4, 2, 0), "Blender minimum predates extension support")
    if "blender_version_max" in data:
        require(version(data["blender_version_max"]) > minimum, "invalid Blender compatibility range")
    # Older versions of these add-ons also expose static legacy metadata.
    for node in init.body:
        if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "bl_info" for target in node.targets):
            continue
        info = ast.literal_eval(node.value)
        require(isinstance(info, dict), "invalid bl_info")
        for legacy, key in (("version", "version"), ("blender", "blender_version_min")):
            if legacy in info:
                require(info[legacy] == version(data[key]), f"bl_info {legacy} differs from manifest {key}")
    require(not ARCHIVE_KEYS.intersection(data), "manifest contains reserved archive metadata")
    return data


def read_json(path):
    return json.loads(path.read_text())


def rows(root):
    index = read_json(root / "index.json")
    require(index.get("version") == "v1" and isinstance(index.get("data"), list), "invalid feed schema")
    result = {}
    for row in index["data"]:
        identifier = row["id"]
        require(identifier not in result, f"duplicate index ID: {identifier}")
        result[identifier] = row
    return result


def run(*command):
    subprocess.run(command, check=True)


def validate(root, blender_cli=None):
    index = rows(root)
    sources = read_json(root / "sources.json")
    require(index.keys() == sources.keys(), "feed and source registry IDs differ")
    errors = []
    expected_archives = set()
    for identifier, row in index.items():
        try:
            source = sources[identifier]
            current, target = version(row["version"]), version(source["version"])
            require(current == target, f"{'outdated package' if current < target else 'unapproved version'}: "
                    f"feed {row['version']}, source {source['version']}")
            require(re.fullmatch(r"[a-z][a-z0-9_]*", identifier), "invalid index ID")
            name = f"{identifier}-{row['version']}.zip"
            expected_archives.add(name)
            require(row["archive_url"] == f"./{name}", "invalid archive URL")
            path = root / name
            require(path.is_file() and not path.is_symlink(), f"missing archive or symlink: {name}")
            require(type(row["archive_size"]) is int and path.stat().st_size == row["archive_size"],
                    "archive size mismatch")
            sha256 = digest(path)
            require(row["archive_hash"] == f"sha256:{sha256}", "index SHA-256 mismatch")
            require(source["sha256"] == sha256, "source release SHA-256 mismatch")
            data = manifest(path)
            for key in ("blender_version_min", "blender_version_max", "platforms", "wheels"):
                require(data.get(key) == row.get(key), f"inconsistent compatibility declaration: {key}")
            require({key: value for key, value in row.items() if key not in ARCHIVE_KEYS} == {key: value for key, value in data.items() if key != "build"},
                    "index metadata differs from archive manifest")
            if blender_cli:
                run(sys.executable, str(blender_cli), "validate", str(path))
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, SyntaxError, zipfile.BadZipFile,
                subprocess.CalledProcessError) as exc:
            errors.append(f"{identifier}: {exc}")
    if not errors:
        unexpected = {path.name for path in root.glob("*.zip")} - expected_archives
        require(not unexpected, f"unindexed ZIPs: {', '.join(sorted(unexpected))}")
    require(not errors, "\n".join(errors))


def latest(source):
    release = json.loads(subprocess.check_output([
        "gh", "release", "view", "-R", source["repo"], "--json", "tagName,assets,isDraft,isPrerelease"
    ], text=True))
    tag = release["tagName"]
    require(not (release["isDraft"] or release["isPrerelease"]), f"{tag} is not a stable release")
    number = tag.removeprefix("v")
    version(number)
    name = source["asset"].format(version=number)
    assets = [item for item in release["assets"] if item["name"] == name]
    require(len(assets) == 1, f"{source['repo']} {tag}: expected release asset {name}")
    sha = assets[0].get("digest") or ""
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", sha), f"{name}: upstream SHA-256 unavailable")
    return tag, number, name, sha[7:]


def audit(root):
    errors = []
    for identifier, source in read_json(root / "sources.json").items():
        try:
            _, number, _, sha = latest(source)
            print(f"{identifier}: pinned {source['version']}, latest stable {number}")
            require((number, sha) == (source["version"], source["sha256"]),
                    "source release version or SHA-256 differs; review before staging")
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"{identifier}: {exc}")
    require(not errors, "\n".join(errors))


def stage(root, identifier, cli, destination):
    """Produce a validated feed in a new directory; leave the checkout intact."""
    require(not destination.exists(), f"destination already exists: {destination}")
    validate(root, cli)
    sources = read_json(root / "sources.json")
    source = sources[identifier]
    tag, number, asset, sha = latest(source)
    require(version(number) > version(source["version"]), f"{tag} is not newer than the pinned version")
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        work = Path(directory)
        feed = work / "feed"
        feed.mkdir()
        run("gh", "release", "download", tag, "-R", source["repo"], "-p", asset, "-D", str(work))
        package = work / asset
        require(digest(package) == sha, f"{asset}: source release SHA-256 mismatch")
        data = manifest(package)
        require((data["id"], data["version"]) == (identifier, number), "source archive ID/version mismatch")
        previous = rows(root)[identifier]
        for key in ("blender_version_min", "blender_version_max", "platforms", "wheels"):
            require(data.get(key) == previous.get(key),
                    f"compatibility changed ({key}); review and handle as an explicit feed migration")
        for path in [*root.glob("*.zip"), root / "index-template.html", *root.glob("blender_repo.toml")]:
            if path.name != previous["archive_url"][2:]:
                shutil.copy2(path, feed)
        shutil.copy2(package, feed / f"{identifier}-{number}.zip")
        source.update(version=number, sha256=sha)
        (feed / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
        run(sys.executable, str(cli), "server-generate", "--repo-dir", str(feed),
            "--html", "--html-template", str(feed / "index-template.html"))
        # Retain repository-level settings across Blender generator versions.
        original = read_json(root / "index.json")
        original["data"] = read_json(feed / "index.json")["data"]
        (feed / "index.json").write_text(json.dumps(original, indent=2) + "\n")
        validate(feed, cli)
        feed.rename(destination)
    print(f"Staged {identifier} {number} at {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--blender-cli", type=Path, help="Path to Blender's bl_pkg/cli/blender_ext.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("audit")
    staging = commands.add_parser("stage")
    staging.add_argument("id")
    staging.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "stage":
            require(args.blender_cli is not None, "stage requires --blender-cli")
            stage(args.root.resolve(), args.id, args.blender_cli.resolve(), args.destination.resolve())
        else:
            validate(args.root, args.blender_cli)
            if args.command == "audit":
                audit(args.root)
            print("Feed validation passed")
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
