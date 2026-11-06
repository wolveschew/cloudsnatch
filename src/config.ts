import dotenv from "dotenv";

dotenv.config();

export const config = {
  sourceUrl: process.env.SOUNDCLOUD_SOURCE_URL ?? "https://soundcloud.com/your-source",
  targetUrl: process.env.SOUNDCLOUD_TARGET_URL ?? "https://soundcloud.com/your-target",
  clientId: process.env.SOUNDCLOUD_CLIENT_ID ?? "",
  sourceToken: process.env.SOUNDCLOUD_SOURCE_TOKEN ?? "",
  targetToken: process.env.SOUNDCLOUD_TARGET_TOKEN ?? "",
  outputDir: process.env.OUTPUT_DIR ?? "exports",
  stateFile: process.env.STATE_FILE ?? "state.json",
  failedFile: process.env.FAILED_FILE ?? "failed.json",
  dryRun: (process.env.DRY_RUN ?? "false").toLowerCase() === "true",
};
