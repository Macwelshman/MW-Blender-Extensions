# MW Blender Extensions

Official Blender Extension packages for MW Blender add-ons.

This repository is a distribution layer only. Each add-on keeps its own source
repository, development branches, issues, and releases. Only tested packages are
published here for installation and updates through Blender.

## Add this repository to Blender

### Drag and drop

1. Open the [MW Blender Extensions installation page](https://macwelshman.github.io/MW-Blender-Extensions/).
2. Keep Blender open beside the web browser.
3. Drag the linked package ID for the extension you want from the page into Blender.
4. Confirm Blender's installation prompt.

The download link includes the MW repository address, so Blender adds the
repository while installing the extension. Future releases then appear through
**Check for Updates**.

### Add manually

In Blender 5.2:

1. Open **Edit > Preferences > Get Extensions**.
2. Open the repositories menu and choose **Repositories**.
3. Add a remote repository using:

   `https://raw.githubusercontent.com/Macwelshman/MW-Blender-Extensions/main/index.json`

4. Sync the repository.
5. Search for **MW PBR Material** and install it.

## Published extensions

- [MW PBR Material](https://github.com/Macwelshman/MW-PBR-Material) 0.6.5
- [MW CS2 PBR Material](https://github.com/Macwelshman/MW-CS2-PBR-Material) 2.6.14
- [MW CS2 Batch Exporter](https://github.com/Macwelshman/MW-CS2-Batch-Exporter) 0.1.24
- [MW CS2 Window Distributor](https://github.com/Macwelshman/MW_CS2_Window_Distributor) 2.7.3

Package metadata, compatibility, and licensing are declared in each extension's
`blender_manifest.toml`.
