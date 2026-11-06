<div align="center">

# 🎧 SoundArchive Desktop App

Want to keep a copy of your public SoundCloud likes and playlists? SoundArchive Desktop App helps you save them as files on your computer—no account login needed.

[![Latest release](https://img.shields.io/github/v/release/wolveschew/soundarchive-desktop-app?style=for-the-badge&color=ff5500)](https://github.com/wolveschew/soundarchive-desktop-app/releases/latest)
[![Build status](https://img.shields.io/github/actions/workflow/status/wolveschew/soundarchive-desktop-app/build-desktop.yml?branch=main&style=for-the-badge&label=Windows%20%26%20macOS%20builds)](https://github.com/wolveschew/soundarchive-desktop-app/actions/workflows/build-desktop.yml)

## 🚀 Install first

Choose the button for your computer to download the installer:

<a href="https://github.com/wolveschew/soundarchive-desktop-app/releases/latest/download/SoundCloudArchiveSetup.exe"><img alt="Download Windows installer" src="https://img.shields.io/badge/Download-Windows%20installer-0078D4?style=for-the-badge&logo=windows&logoColor=white"></a>
&nbsp;
<a href="https://github.com/wolveschew/soundarchive-desktop-app/releases/latest/download/SoundCloudArchive.dmg"><img alt="Download macOS app" src="https://img.shields.io/badge/Download-macOS%20app-555555?style=for-the-badge&logo=apple&logoColor=white"></a>

[See all releases](https://github.com/wolveschew/soundarchive-desktop-app/releases)

📌 Ready-to-install downloads are available for Windows and macOS. A Linux installer is not currently published.

</div>

> 👋 **Just want to use the app?** You’re in the right place. Choose your computer above, download the file, and follow the short steps below. You don’t need to open GitHub Actions or download any source code.

### 🪟 Windows

1. Select **Download Windows installer** above and wait for the installer to finish downloading.
2. Open the downloaded file. If Windows SmartScreen warns that the app is unsigned, check that it came from this repository's Releases page before choosing **Run anyway**.
3. Keep the suggested install folder, or choose another folder where your Windows account can create files. Protected folders such as `C:\Program Files` need extra permissions and are not suitable for this per-user installer.
4. Finish setup and open **SoundArchive Desktop App** from your Start menu. The installer adds Microsoft's WebView2 Runtime if it’s needed.

### 🍎 macOS

1. Select **Download macOS app** above and open the downloaded disk image.
2. Drag **SoundArchive Desktop App** to your **Applications** folder.
3. The app is unsigned. The first time you open it, Control-click the app, choose **Open**, and confirm the macOS warning.

## 🎵 Next: export your collections

1. Paste a **public SoundCloud profile link**, such as `https://soundcloud.com/artist`.
2. Select **Export collections** and keep the app open while it works.
3. When it’s done, download `likes.json`, `playlists.json`, and the status report from the results.

The app exports public likes and playlists only. **Following lists are not supported.** If your connection drops, start the same profile again to continue from a local checkpoint. The app refetches the collection from the beginning and skips items it already saved; it does not jump directly to the last saved item. Choose **Re-fetch completed collections** to discard saved progress for that category and start it again.

## 📁 Where to find your files

Your archive and appearance settings stay in a folder on your computer. The existing **SoundCloud Archive** folder name is kept so earlier exports and checkpoints remain available:

| System | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\SoundCloud Archive` |
| macOS | `~/Library/Application Support/SoundCloud Archive` |
| Linux | `$XDG_DATA_HOME/soundcloud-archive` or `~/.local/share/soundcloud-archive` |

`likes.json` and `playlists.json` contain the records the public extractor returned. `report.json` lists each category's status and any errors. `state.json` tracks checkpoint status. Appearance preferences are saved in `settings.json`.

## 🔒 Privacy and what to expect

- No login, password, cookies, or account token is requested.
- Only publicly accessible data returned by yt-dlp's maintained SoundCloud extractor is used. No undocumented endpoints are called.
- An export marked **complete** means the extractor finished returning items normally. SoundCloud visibility, pagination, rate limits, and extractor behavior can limit results; complete coverage has not been verified.
- The app does not import data, automate likes or follows, or evade bot detection.
- Exports are sequential metadata requests; audio is not downloaded. No periodic status polling or other background export work runs while idle.

## 🧰 Need a hand?

**Windows says it cannot install to the selected folder:** choose the suggested folder under your Windows user account, or another folder where you can create files. The installer checks permissions before proceeding.

**The app does not open:** install the latest version from the download button above and try again. The Windows app needs Microsoft Edge WebView2 Runtime; setup installs it if needed. If startup still fails, check `startup-error.log` in the local data folder listed above and share its contents when asking for help.

**A collection failed or looks incomplete:** check that the SoundCloud profile and collection are public, review `report.json`, and try again later. A successful export only includes items the public extractor could return.

**Unsigned app warning:** this project currently does not code-sign its Windows or macOS app. Only continue if you downloaded it from this repository's Releases page and trust the source.

## 🛠️ For contributors

Run the offline test suite with Python 3.10 or later:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests and builds Windows and macOS installers. A version-tagged release is published after both platform builds succeed. The download buttons above always point to the latest published installers.
