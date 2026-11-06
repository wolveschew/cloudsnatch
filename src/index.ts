import path from "path";
import { config } from "./config.js";
import { ensureDir } from "./storage.js";
import { resolveUserId } from "./soundcloud.js";
import { exportCategory } from "./export.js";
import { importCategory } from "./import.js";

async function main() {
  const categories = ["likes", "followings", "playlists"] as const;

  await ensureDir(config.outputDir);

  console.log("Source URL:", config.sourceUrl);
  console.log("Target URL:", config.targetUrl);

  if (!config.clientId) {
    console.warn("No SoundCloud client id provided. Public resolve may fail for some endpoints.");
  }

  if (!config.sourceToken && !config.clientId) {
    console.warn("Without a SoundCloud access token, only public profile metadata may be available.");
  }

  try {
    const sourceUserId = await resolveUserId(config.sourceUrl, config.clientId, config.sourceToken);
    console.log("Resolved source user id:", sourceUserId);
  } catch (error) {
    console.error("Could not resolve source user id.");
    console.error(error);
    process.exitCode = 1;
    return;
  }

  const exported: Record<string, any[]> = {};

  for (const category of categories) {
    console.log(`\n=== Exporting ${category} ===`);
    const records = await exportCategory(category, config.sourceUrl, config.clientId, config.sourceToken);
    exported[category] = records;
    console.log(`[${category}] exported ${records.length} records`);
  }

  if (config.dryRun) {
    console.log("Dry run only. No import was executed.");
    return;
  }

  if (!config.targetToken) {
    console.warn("No target token was provided. Import step was skipped.");
    return;
  }

  console.log("\n=== Importing into target account ===");
  for (const category of categories) {
    const records = exported[category] ?? [];
    const result = await importCategory(category, records, config.targetToken, false);
    console.log(`[${category}] done=${result.done} failed=${result.failed} skipped=${result.skipped}`);
  }
}

main().catch((error) => {
  console.error("Fatal error:");
  console.error(error);
  process.exit(1);
});
