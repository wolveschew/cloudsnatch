import { config } from "./config.js";
import { rateLimitPause } from "./soundcloud.js";
import { logFailure } from "./export.js";
import type { Category, ExportRecord } from "./types.js";

export async function importCategory(
  category: Category,
  records: ExportRecord[],
  token?: string,
  dryRun = false
) {
  const summary = { done: 0, failed: 0, skipped: 0 };

  for (const record of records) {
    try {
      await rateLimitPause(`import:${category}`, 2200);

      if (dryRun) {
        summary.skipped += 1;
        continue;
      }

      if (category === "likes") {
        const trackId = record.raw?.track?.id ?? record.raw?.id;
        if (!trackId) throw new Error("Missing track id");

        await fetch("https://api.soundcloud.com/me/favorites", {
          method: "POST",
          headers: {
            Authorization: `OAuth ${token ?? ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ track_id: trackId }),
        });
      } else if (category === "followings") {
        const userId = record.raw?.user?.id ?? record.raw?.id;
        if (!userId) throw new Error("Missing user id");

        await fetch("https://api.soundcloud.com/me/followings", {
          method: "POST",
          headers: {
            Authorization: `OAuth ${token ?? ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ user_id: userId }),
        });
      } else if (category === "playlists") {
        const payload = {
          title: record.raw?.title ?? "Imported Playlist",
          sharing: "private",
          tracks: Array.isArray(record.raw?.tracks)
            ? record.raw.tracks.map((item: any) => ({ id: item.id ?? item.track?.id }))
            : [],
        };

        await fetch("https://api.soundcloud.com/playlists", {
          method: "POST",
          headers: {
            Authorization: `OAuth ${token ?? ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
      } else {
        throw new Error(`Unsupported category: ${category}`);
      }

      summary.done += 1;
    } catch (error) {
      summary.failed += 1;
      await logFailure(category, record.id, category, error, record.raw, true);
      console.error(`[${category}] failed item ${record.id}:`, error);
    }
  }

  return summary;
}
