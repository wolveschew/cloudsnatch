# SoundCloud Archive

A simple local desktop app for saving **publicly accessible** SoundCloud likes and playlists as JSON. The app does not ask for an account login, password, cookies, or token. It only uses yt-dlp's maintained public SoundCloud extractor; it does not call undocumented endpoints.

## Install the Windows release

Download `SoundCloudArchiveSetup.exe` from the repository's **Releases** page, run it, and follow the installer prompts. The installer is per-user and does not require administrator permission. It installs Microsoft's WebView2 Runtime if needed, adds a Start menu shortcut, and can optionally add a desktop shortcut. The packaged app is unsigned, so Windows SmartScreen may show a security warning; verify that the release is from this repository before choosing **Run anyway**.

Releases are created automatically when a `v*` version tag is pushed, after the Windows and macOS builds and tests succeed. The Windows release asset is an `.exe` installer; the macOS release asset is an unsigned `.dmg`. On macOS, Gatekeeper may require Control-clicking the app and choosing **Open** the first time.

Pull requests and normal pushes build downloadable CI artifacts but do not publish a release. To try those builds before a tagged release, download the Windows installer or macOS disk image from a successful **Build desktop apps** workflow run.

## Run from source

Install Python 3.10 or later, then from the repository directory:

**Windows**

```powershell
py -m pip install -r requirements.txt
py desktop_app.py
```

**macOS**

```sh
python3 -m pip install -r requirements.txt
python3 desktop_app.py
```

The app opens in a native window and serves its interface only on a loopback address. `python app.py` is also available for local browser-based development.

## Data, checkpoints, and status

Exports and resumable checkpoints are saved under your user data directory:

- Windows: `%LOCALAPPDATA%\SoundCloud Archive`
- macOS: `~/Library/Application Support/SoundCloud Archive`
- Linux: `$XDG_DATA_HOME/soundcloud-archive` or `~/.local/share/soundcloud-archive`

`likes.json` and `playlists.json` contain the records returned by the extractor. The app atomically checkpoints every 25 new entries and when a collection ends or fails. Resume refetches the public collection from its beginning and de-duplicates against saved item IDs; it is not a seek into SoundCloud's collection. **Re-fetch completed collections** discards that category's old checkpoint and starts over. `report.json` records per-category status, counts, failures, and the unsupported category; `state.json` records checkpoint status. Incomplete files are retained for recovery and can be downloaded when present.

## Scope and limitations

- Likes and playlists are attempted only for a public profile and only through the supported yt-dlp extractor.
- **Following lists are unsupported.** This app does not claim a verified public method and does not try private or undocumented endpoints.
- A `complete` status means only that the extractor's returned iterator ended normally. This project has not verified live SoundCloud completeness; SoundCloud visibility, pagination, rate limits, and extractor behavior can limit results.
- This is an exporter only. It has no login, account import, automated likes/follows, or bot-detection evasion.
- Appearance preferences (accent color and compact cards) are stored locally in the desktop webview.

## Tests and desktop builds

Run the offline unit tests with:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs those tests and builds the Windows executable and macOS disk image. Local builds require the packaging dependencies and a native build host for each operating system.
