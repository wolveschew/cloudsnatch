# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Users

SoundCloud listeners who want a local copy of metadata from public likes and playlists. They may be unfamiliar with GitHub and want straightforward downloads and instructions. The Android workflow should work comfortably on phones and larger screens.

## Product Purpose

CloudSnatch exports metadata from publicly accessible SoundCloud likes and playlists to local CSV and JSON files. Success means users can see what is being saved, resume interrupted exports, and find their files without signing in to CloudSnatch.

## Positioning

A lightweight, open-source exporter that organizes public collection metadata by profile and makes its local output visible. It does not download audio or require a CloudSnatch account.

## Operating Context

Users paste a public SoundCloud profile URL, inspect per-category progress and errors, and save the resulting files locally. Windows and macOS use a desktop application; Android uses the system Downloads area. A private checkpoint lets users resume an interrupted export.

## Capabilities and Constraints

- Export public likes and playlists as CSV and JSON using yt-dlp's maintained SoundCloud extractor.
- Following and follower lists, private-account access, audio downloads, login, OAuth, cookies, automated likes or follows, and bot-detection evasion are unsupported.
- Export completion reports indicate that the extractor iterator ended normally; they do not prove complete SoundCloud coverage.
- Export data and checkpoints are stored locally. The app has no user account, app backend, advertising, or analytics.
- SoundCloud requests are made directly from the user's device to retrieve public collection metadata. The user controls whether to share exported files from Android.
- Android targets phones and larger displays and places completed exports in `Downloads/CloudSnatch`. App-private checkpoints support resuming after interruption.
- Android release APKs must use a stable signing key held as a protected GitHub Actions secret. Do not publish an unsigned or debug-signed APK as a production release.
- The repository is MIT-licensed. Preserve its license and open-source source code.

## Brand Commitments

- Product name: **CloudSnatch**.
- Product descriptor: **SoundCloud Likes & Playlist Export App** for Windows, macOS, and Android.
- Preserve the existing dark interface, orange accent, readable hierarchy, and direct, friendly copy.
- Android should translate that identity into native Material 3 components rather than wrap or stretch the desktop interface.

## Evidence on Hand

- The working desktop interface, CSV/JSON exporter, checkpoint behavior, and passing offline tests are in the repository.
- A Windows installer and macOS disk image were previously published as SoundSnatch v1.1.0.
- Android is being added as a native Material app; its release APK requires a protected signing key and emulator validation.
- No live SoundCloud completeness audit is available.

## Product Principles

- Public metadata only; no private access workarounds.
- Keep export data on the user's device unless they explicitly share it.
- Make progress, checkpoint state, failures, and output locations clear.
- Prefer lightweight sequential work that runs only when the user starts an export.
- Describe what the extractor does without promising complete coverage.
