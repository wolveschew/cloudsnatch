<div align="center">

# 🎧 SoundSnatch

Save metadata from **public SoundCloud likes and playlists** as CSV and JSON files on your computer. Each profile is kept in its own folder, with live export status and resumable local checkpoints.

[![Latest release](https://img.shields.io/github/v/release/wolveschew/soundsnatch?style=for-the-badge&color=ff5500)](https://github.com/wolveschew/soundsnatch/releases/latest)
[![Build status](https://img.shields.io/github/actions/workflow/status/wolveschew/soundsnatch/build-desktop.yml?branch=main&style=for-the-badge&label=Windows%20%26%20macOS%20builds)](https://github.com/wolveschew/soundsnatch/actions/workflows/build-desktop.yml)

## 🚀 Install first

Choose your computer to download the installer:

<a href="https://github.com/wolveschew/soundsnatch/releases/latest/download/SoundSnatchSetup.exe"><img alt="Download Windows installer" src="https://img.shields.io/badge/Download-Windows%20installer-0078D4?style=for-the-badge&logo=windows&logoColor=white"></a>
&nbsp;
<a href="https://github.com/wolveschew/soundsnatch/releases/latest/download/SoundSnatch.dmg"><img alt="Download macOS app" src="https://img.shields.io/badge/Download-macOS%20app-555555?style=for-the-badge&logo=apple&logoColor=white"></a>

[See all releases](https://github.com/wolveschew/soundsnatch/releases)

Ready-to-install downloads are available for Windows and macOS. A Linux installer is not currently published.

</div>

> 👋 Download the installer for your computer, then follow the steps below. You do not need to open GitHub Actions or download source code.

### 🪟 Windows

1. Download and open **SoundSnatchSetup.exe**.
2. If Windows SmartScreen warns that the app is unsigned, check that you downloaded it from this repository's Releases page before choosing **Run anyway**.
3. Keep the suggested install folder, or choose another folder where your Windows account can create files.
4. Finish setup and launch **SoundSnatch** from the Start menu. Setup installs Microsoft's WebView2 Runtime if needed.

### 🍎 macOS

1. Download and open **SoundSnatch.dmg**.
2. Drag **SoundSnatch** to your **Applications** folder.
3. The app is unsigned. The first time you open it, Control-click the app, choose **Open**, and confirm the macOS warning.

## 🎵 Export public collections

1. Paste a public SoundCloud profile URL, such as `https://soundcloud.com/artist`.
2. Select **Export collections** and keep SoundSnatch open while it works.
3. Expand **Latest collection item** to inspect the JSON record and CSV row as the export runs.
4. Select **Open folder** to show that profile's CSV and JSON files in your system file manager.

Likes and playlists are exported separately. The app reports per-category counts, errors, and completion state; it saves JSON checkpoints every 25 new items and updates the CSV as items arrive. Resuming refetches the public collection from its beginning and skips IDs already present in the checkpoint. It does not seek directly to the last saved item. **Re-fetch completed collections** discards the saved checkpoint for the selected profile and starts again.

### 📂 Files and accounts

Every profile URL is assigned a separate folder so you can export multiple profiles without mixing their files. Open the same profile URL again to resume that profile's checkpoint. On first use, matching archives from the older single-profile layout are copied into that account folder; the originals are left untouched.

| System | Data folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\SoundCloud Archive\accounts` |
| macOS | `~/Library/Application Support/SoundCloud Archive/accounts` |
| Linux | `$XDG_DATA_HOME/soundcloud-archive/accounts` or `~/.local/share/soundcloud-archive/accounts` |

Each account folder contains `likes.json`, `likes.csv`, `playlists.json`, `playlists.csv`, `report.json`, and `state.json` as they become available. JSON retains the metadata returned by the public extractor. CSV includes common fields such as ID, title, URL, uploader, duration, and description. Settings and older exports remain in the existing **SoundCloud Archive** data directory.

## 🔒 Scope and limitations

- Public likes and playlists only. **Following and follower lists are unsupported**; no verified public method is used.
- No SoundCloud login, OAuth, browser-cookie import, private endpoint, automated likes/follows, audio download, or bot-detection evasion.
- SoundSnatch uses yt-dlp's maintained public SoundCloud extractor. Public visibility, pagination, rate limits, and extractor behavior can limit results. A **complete** status means the extractor iterator ended normally; it does not prove that every item was returned.
- SoundcloudSnapshot's old client-ID collection calls and SCDL-GUI-AIO's browser-cookie/private extractor workflow are not integrated. SCDL-GUI-AIO downloads audio; it is not a CSV/JSON collection exporter.
- SoundCloud's current official API requires a registered app and OAuth for user resources. This app does not bypass that authorization. Review SoundCloud's current [API Terms of Use](https://developers.soundcloud.com/docs/api/terms-of-use), including its restrictions on saving or persistently storing User Content, before using any exporter.
- SoundSnatch is not affiliated with or endorsed by SoundCloud.

## 🧰 Troubleshooting

**The folder does not open:** enter a valid public profile URL and choose **Open folder** again. The app creates the profile folder if it does not exist and reports any operating-system error.

**A collection fails or seems incomplete:** confirm the profile and collection are public, review `report.json`, and retry later. The export only contains items the public extractor could return.

**The app does not open:** install the latest release. Windows requires Microsoft Edge WebView2 Runtime; setup installs it if needed. If startup still fails, check `startup-error.log` in the **SoundCloud Archive** data folder (the parent of `accounts` in the table above).

**Unsigned app warning:** only continue if you downloaded SoundSnatch from this repository's Releases page and trust the source.

## 🛠️ For contributors

Run the offline test suite with Python 3.10 or later:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs tests and builds the Windows and macOS apps. A version-tagged release is published only after both platform builds succeed.
