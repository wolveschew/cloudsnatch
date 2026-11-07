<div align="center">

# CloudSnatch — SoundCloud Snapshot Tool

Create local snapshots of **public SoundCloud likes, playlists, and playlist tracks** as CSV and JSON. CloudSnatch is an open-source snapshot tool for **Windows, macOS, and Android**. It runs on your device: no CloudSnatch account, sign-in, or analytics.

[![Latest release](https://img.shields.io/github/v/release/wolveschew/cloudsnatch?style=for-the-badge&color=ff5500)](https://github.com/wolveschew/cloudsnatch/releases/latest)
[![Builds](https://img.shields.io/github/actions/workflow/status/wolveschew/cloudsnatch/build-desktop.yml?branch=main&style=for-the-badge&label=Windows%20macOS%20Android)](https://github.com/wolveschew/cloudsnatch/actions/workflows/build-desktop.yml)
[![MIT license](https://img.shields.io/github/license/wolveschew/cloudsnatch?style=for-the-badge)](LICENSE)

## DOWNLOAD AND INSTALL

<a href="https://github.com/wolveschew/cloudsnatch/releases/latest"><img alt="Download CloudSnatch for Windows" src="https://img.shields.io/badge/Download-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white"></a>
&nbsp;
<a href="https://github.com/wolveschew/cloudsnatch/releases/latest"><img alt="Download CloudSnatch for macOS" src="https://img.shields.io/badge/Download-macOS-555555?style=for-the-badge&logo=apple&logoColor=white"></a>
&nbsp;
<a href="https://github.com/wolveschew/cloudsnatch/releases/latest/download/CloudSnatch.apk"><img alt="Download CloudSnatch for Android" src="https://img.shields.io/badge/Download-Android%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white"></a>

[Browse all releases](https://github.com/wolveschew/cloudsnatch/releases)

</div>

### Windows

1. Download and open the latest Windows `.exe` from [Releases](https://github.com/wolveschew/cloudsnatch/releases/latest).
2. If Windows warns that the app is unsigned, verify you downloaded it from this repository's Releases page before continuing.
3. Keep the suggested install folder, then open CloudSnatch from the Start menu. Setup installs Microsoft Edge WebView2 if needed.

### macOS

1. Download and open the latest `.dmg` from [Releases](https://github.com/wolveschew/cloudsnatch/releases/latest).
2. Drag **CloudSnatch** to Applications.
3. The app is unsigned. The first time you open it, Control-click the app, choose **Open**, and confirm the macOS warning.

### Android

1. Download [CloudSnatch for Android](https://github.com/wolveschew/cloudsnatch/releases/latest/download/CloudSnatch.apk).
2. Open the downloaded APK and follow Android's install prompts. Android 10 or newer is required.
3. If Android asks, allow installation from the app you used to download the APK.

## Create your first snapshot

1. Paste a public SoundCloud profile URL, such as `https://soundcloud.com/artist`.
2. Select **Create snapshot** (or **Create snapshot or resume** on Android) and keep the app open while it works.
3. Follow the progress bar and per-category status. When a reliable total is available, the bar shows progress toward it; otherwise it stays indeterminate rather than guessing.
4. Watch the live track-ID list as liked tracks and tracks inside public playlists are found.
5. Open the saved files:
   - **Windows and macOS:** choose **Open folder** for that profile.
   - **Android:** current files are saved in `Downloads/CloudSnatch/<profile>/`; use **Open Downloads** or **Share files**.

Each profile has a separate folder. Snapshots are timestamped and kept locally until you clear that profile's history. Compare the latest two snapshots to see how many likes, playlists, and playlist tracks were added or removed; categories that did not finish in both snapshots are marked as unavailable rather than compared. Clearing history keeps the current export files. On Android, snapshot history stays in the app's private storage and comparison is available in the app.

Each run refreshes completed collections to create a current snapshot. If it finds an interrupted collection, it resumes from that checkpoint by refetching from the beginning and skipping IDs already saved; it does not seek directly to the last saved item. JSON checkpoints are saved every 25 new items, and CSV rows are flushed as items arrive. **Start over** discards the selected profile's incomplete checkpoints and replaces its current files, while keeping saved snapshot history.

## What it does—and does not do

- Saves metadata from **public likes, playlists, and tracks inside public playlists** as CSV and JSON. Playlist contents are expanded with yt-dlp's maintained SoundCloud extractor; no audio is downloaded.
- Shows track IDs while they are found and creates timestamped local snapshots that can be compared later.
- Keeps checkpoints and working data on your device. Android asks for no broad storage permission; it uses Android's Downloads media collection for files it creates.
- Makes public SoundCloud requests directly from your device using yt-dlp's maintained SoundCloud extractor. The app has no CloudSnatch server, ads, analytics, or account system.
- **Does not support following or follower lists**, private accounts, login, OAuth, browser cookies, audio downloads, automated likes/follows, private endpoints, or bot-detection evasion.
- A **complete** status means the extractor finished normally. It does not prove that every item was returned; public visibility, pagination, rate limits, and extractor behavior can limit results.

CloudSnatch is independent and is not affiliated with or endorsed by SoundCloud. Review SoundCloud's current [API Terms of Use](https://developers.soundcloud.com/docs/api/terms-of-use) before archiving content.

## Developer details

CloudSnatch is MIT-licensed. The Windows and macOS desktop apps use Python, Flask, pywebview, and yt-dlp. Android uses a native Kotlin/Jetpack Compose interface and the same Python exporter packaged with Chaquopy. Android writes only to its private app directory and to the Downloads files it creates; it does not request access to the rest of the device's storage.

### Run the tests

```sh
python -m unittest discover -s tests -v
```

Android builds use JDK 17, Gradle 8.11.1, and Python 3.12:

```sh
gradle -p android :app:testDebugUnitTest :app:assembleDebug
gradle -p android :app:connectedDebugAndroidTest
```

The GitHub Actions workflow runs the desktop tests and builds, Android unit tests, and an Android emulator UI test. A version-tagged release publishes Windows and macOS installers and a **release-signed** Android APK after all platform jobs pass.

### Privacy and security

There is no app telemetry, advertising, user account, or CloudSnatch-operated export server. Public collection requests go directly from the app to SoundCloud and any hosts used by its public extractor. Export files are local unless you explicitly share them from Android. Report security issues through GitHub's private **Security → Advisories → Report a vulnerability** flow for this repository.
