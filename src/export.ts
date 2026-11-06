import path from "path";
import { config } from "./config.js";
import { readJsonFile, writeJsonFile } from "./storage.js";
import { fetchCollection, rateLimitPause } from "./soundcloud.js";
import type { Category, ExportRecord, State } from "./types.js";

export async function loadState() {
  const filePath = path.resolve(process.cwd(), config.stateFile);
  const fallback: State = {
    version: 1,
    completed: {},
    exports: {},
    lastOffsets: {},
    lastRun: new Date().toISOString(),
  };

  return readJsonFile<State>(filePath, fallback);
}

export async function saveState(state: State) {
  const filePath = path.resolve(process.cwd(), config.stateFile);
  await writeJsonFile(filePath, state);
}

export async function logFailure(
  category: Category,
  itemId: string | number,
  kind: string,
  error: unknown,
  payload?: any,
  retryable = true
) {
  const filePath = path.resolve(process.cwd(), config.failedFile);
  const existing = await readJsonFile<any[]>(filePath, []);

  existing.push({
    category,
    id: itemId,
    kind,
    error: String(error),
    retryable,
    payload,
    timestamp: new Date().toISOString(),
  });

  await writeJsonFile(filePath, existing);
}

export async function exportCategory(
  category: Category,
  userId: string | number,
  clientId: string,
  token?: string
): Promise<ExportRecord[]> {
  const outputDir = path.resolve(process.cwd(), config.outputDir);
  const filePath = path.join(outputDir, `${category}.json`);

  const state = await loadState();
  const offsetSeed = state.lastOffsets?.[category] ?? 0;
  const prior = state.exports?.[category] ?? [];

  let offset = offsetSeed;
  const all: ExportRecord[] = [...prior];

  while (true) {
    await rateLimitPause(category, 1600);

    let page: any[] = [];
    try {
      page = await fetchCollection(category, userId, clientId, token, offset, 200);
    } catch (error) {
      console.error(`[${category}] fetch failed at offset ${offset}:`, error);
      break;
    }

    if (!page.length) {
      break;
    }

    const batch: ExportRecord[] = page.map((item) => ({
      id: item?.id ?? `${category}:${Math.random()}`,
      raw: item,
      sourceUrl: item?.permalink_url ?? item?.user?.permalink_url ?? item?.track?.permalink_url,
      createdAt: new Date().toISOString(),
    }));

    all.push(...batch);
    offset += page.length;

    const nextState: State = {
      ...state,
      exports: {
        ...state.exports,
        [category]: all,
      },
      lastOffsets: {
        ...state.lastOffsets,
        [category]: offset,
      },
      completed: {
        ...state.completed,
        [category]: false,
      },
      lastRun: new Date().toISOString(),
    };

    await saveState(nextState);
    await writeJsonFile(filePath, all);

    if (page.length < 200) {
      break;
    }
  }

  const finalState: State = {
    ...state,
    exports: {
      ...state.exports,
      [category]: all,
    },
    completed: {
      ...state.completed,
      [category]: true,
    },
    lastRun: new Date().toISOString(),
  };

  await saveState(finalState);
  await writeJsonFile(filePath, all);

  return all;
}
