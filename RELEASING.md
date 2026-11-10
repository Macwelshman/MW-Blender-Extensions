# Release procedure

The feed distributes the exact ZIP from each add-on's latest stable GitHub
release. `sources.json` maps extension IDs to their source repositories,
versioned release asset names, and approved versions and SHA-256 digests.
A working-tree manifest can be ahead of a release; it is not a publishable
artifact. Keep existing extension IDs and the public repository URL stable.

1. Install Python 3.11+ and authenticate the GitHub CLI (`gh`). From an
   up-to-date feed checkout, run `python3 scripts/feed.py audit`. A newly
   released source version makes this command fail until the feed is updated.
   Missing assets, unavailable digests, and GitHub errors also fail the audit.
2. Stage the intended ID in a **new** local directory. Set `BLENDER_EXT_CLI`
   to the standalone `bl_pkg/cli/blender_ext.py` from your Blender installation
   or use the pinned Blender 4.5.0 source script from the validation workflow.

   ```sh
   python3 scripts/feed.py --blender-cli "$BLENDER_EXT_CLI" \
     stage mw_cs2_batch_exporter /absolute/path/to/new-candidate
   ```

   Staging downloads the exact asset from the latest stable release, verifies
   its GitHub digest, checks its manifest and compatibility against the old
   entry, and regenerates the JSON and drag-to-install HTML. It validates the
   candidate before making that directory available. It leaves the checkout
   untouched. If the release intentionally changes its compatibility range,
   review that change separately before updating the ZIP and regenerating
   the index and HTML with Blender's `server-generate` command.
3. Review the candidate diff. Copy the new ZIP, `index.json`, `index.html`, and
   `sources.json` into the review checkout, remove the superseded ZIP, and
   update the published versions in `README.md`. The index must continue to
   list one package per ID. Run:

   ```sh
   python3 -m unittest discover -s tests -v
   python3 scripts/feed.py --blender-cli "$BLENDER_EXT_CLI" audit
   ```

   CI runs the fixture tests and Blender manifest validator on pushes and
   pull requests, and checks for upstream drift daily. It has read-only
   permissions. Neither CI nor the staging tool publishes or pushes.
4. Before approval, smoke-test the upgrade in a disposable Blender profile.
   For Batch Exporter 0.1.26, copy the baseline index and ZIPs from feed commit
   `f3a30e5` into a separate directory. Then run on macOS with Flue installed:

   ```sh
   python3 tests/run_flue.py /absolute/path/to/baseline /absolute/path/to/candidate
   ```

   This version-specific smoke test uses a local file repository, installs
   and enables 0.1.25, syncs the candidate at the same URL, checks that
   Blender reports an update, and verifies the installed 0.1.26 manifest and
   enabled add-on. Use `--blender` to select another Blender executable.
5. Obtain approval before publishing. Once approved, publish the reviewed
   feed changes together so the index never points to a missing ZIP. Sync
   the public URL and confirm Blender detects the update. That public
   post-publication check is intentionally outside local staging.

## 0.1.26 candidate — 10 November 2026

| Extension ID | Local source manifest | Latest stable release | Published index / ZIP | Candidate | Blender minimum in candidate |
| --- | --- | --- | --- | --- | --- |
| `mw_cs2_batch_exporter` | 0.1.26 | 0.1.26 | 0.1.25 / 0.1.25 | 0.1.26 | 4.2.0 |
| `mw_cs2_pbr_material` | 2.6.15 | 2.6.14 | 2.6.14 / 2.6.14 | 2.6.14 | 5.0.0 |
| `mw_cs2_window_distributor` | 2.7.6 | 2.7.6 | 2.7.6 / 2.7.6 | 2.7.6 | 5.2.0 |
| `mw_pbr_material` | 0.6.5 | 0.6.5 | 0.6.5 / 0.6.5 | 0.6.5 | 5.0.0 |

The feed's current commit, `f3a30e5`, published Batch Exporter 0.1.25 on
19 September 2026 UTC. The source repository published 0.1.26 on
3 November 2026 UTC without a corresponding feed update. The candidate ZIP
is byte-for-byte identical to the GitHub release asset and the local
`dist` ZIP: **14,020 bytes**, SHA-256
`7ccef9f49b2ea8b1500ffba4a7381b54f81db3b0a2f74973ceddd152ff22b803`.
The ID and minimum Blender version are unchanged, and no maximum is
declared. The other three ZIPs are unchanged and their digests match
their GitHub release assets; they did not need to be downloaded again.

No stable CS2 PBR Material 2.6.15 source ZIP was found. Its local manifest
adds a 5.2.0 maximum; the 2.6.14 release declares no maximum. The candidate
does not copy compatibility metadata from the local 2.6.15 manifest.

The fixture suite passed 12 tests, covering valid and stale packages,
incorrect sizes, digest mismatches, damaged ZIPs, invalid manifests,
compatibility disagreements, and invalid archive URLs. Blender's
standalone manifest validator accepted all four archives. The GitHub
audit detected the published baseline's Batch Exporter lag and accepted
the candidate. Clean profiles on Blender 5.3.0 RC and 5.3.0 Beta each
installed and enabled 0.1.25, detected exactly one update, installed and
enabled 0.1.26, and then reported zero updates. The minimum supported Blender 4.2 runtime and
the public feed after publication were not tested. GitHub Actions was
not run remotely.
