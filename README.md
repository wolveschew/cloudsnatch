<div align="center">

# CloudSnatch — SoundCloud Likes & Playlist Export App

Save metadata from **public SoundCloud likes and playlists** as CSV and JSON files. CloudSnatch is an open-source app for **Windows, macOS, and Android**. It runs on your device: no CloudSnatch account, sign-in, or analytics.

[![Latest release](https://img.shields.io/github/v/release/wolveschew/cloudsnatch?style=for-the-badge&color=ff5500)](https://github.com/wolveschew/cloudsnatch/releases/latest)
[![Builds](https://img.shields.io/github/actions/workflow/status/wolveschew/cloudsnatch/build-desktop.yml?branch=main&style=for-the-badge&label=Windows%20macOS%20Android)](https://github.com/wolveschew/cloudsnatch/actions/workflows/build-desktop.yml)
[![MIT license](https://img.shields.io/github/license/wolveschew/cloudsnatch?style=for-the-badge)](LICENSE)

## Install first

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

## Export your public collections

1. Paste a public SoundCloud profile URL, such as `https://soundcloud.com/artist`.
2. Select **Export or resume** and keep the app open while it works.
3. Watch likes and playlist status, counts, errors, and the latest CSV/JSON item as it is processed.
4. Open the saved files:
   - **Windows and macOS:** choose **Open folder** for that profile.
   - **Android:** files are saved in `Downloads/CloudSnatch/<profile>/`; use **Open Downloads** or **Share files**.

Each profile has a separate folder. JSON checkpoints are saved every 25 new items; CSV rows are flushed as items arrive. Resuming refetches the public collection from the beginning and skips IDs already in the saved checkpoint. It does not seek directly to the last saved item. **Start over** replaces the files for the selected profile only.

## What it does—and does not do

- Exports metadata from **public likes and playlists** as CSV and JSON.
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

Android release signing is managed by the repository's release workflow. The workflow verifies the APK before publishing it.

### Privacy and security

There is no app telemetry, advertising, user account, or CloudSnatch-operated export server. Public collection requests go directly from the app to SoundCloud and any hosts used by its public extractor. Export files are local unless you explicitly share them from Android. Report security issues through GitHub's private **Security → Advisories → Report a vulnerability** flow for this repository.
