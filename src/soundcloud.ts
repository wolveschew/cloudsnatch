import { sleep, randomBetween } from "./storage.js";

export const SOUND_CLOUD_API = "https://api.soundcloud.com";

export async function rateLimitPause(label: string, minMs = 1500) {
  const delay = Math.round(minMs + randomBetween(300, 1400));
  console.log(`[${label}] sleeping ${delay}ms`);
  await sleep(delay);
}

export async function safeJsonFetch<T = any>(
  input: string,
  options: {
    method?: string;
    params?: Record<string, string | number | undefined>;
    headers?: Record<string, string>;
    body?: any;
    token?: string;
  } = {}
): Promise<T> {
  const url = new URL(input);
  const { method = "GET", params = {}, headers = {}, body, token } = options;

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    "User-Agent": "soundcloud-migration-tool/1.0",
    ...headers,
  };

  if (token) {
    finalHeaders.Authorization = `OAuth ${token}`;
  }

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }

  let attempt = 0;

  while (attempt < 8) {
    attempt += 1;

    try {
      const response = await fetch(url.toString(), {
        method,
        headers: finalHeaders,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });

      if (response.status === 429) {
        const retryAfter = Number(response.headers.get("retry-after") ?? "0");
        const waitMs =
          Math.max(retryAfter * 1000, 5000 * attempt) +
          Math.round(randomBetween(400, 1700));
        console.warn(`[429] ${url.toString()} -> backoff ${waitMs}ms`);
        await sleep(waitMs);
        continue;
      }

      if (response.status >= 500) {
        const waitMs = 2000 * attempt + Math.round(randomBetween(500, 1600));
        console.warn(`[server-error] ${url.toString()} -> retry ${waitMs}ms`);
        await sleep(waitMs);
        continue;
      }

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status} for ${url.toString()}: ${text}`);
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        return (await response.json()) as T;
      }

      return (await response.text()) as unknown as T;
    } catch (error) {
      if (attempt >= 8) {
        throw error;
      }

      const waitMs = 1500 * attempt + Math.round(randomBetween(300, 1200));
      console.warn(`[retry] ${url.toString()} -> ${String(error)} -> waiting ${waitMs}ms`);
      await sleep(waitMs);
    }
  }

  throw new Error(`Failed permanently while calling ${input}`);
}

export async function resolveUserId(sourceUrl: string, clientId: string, token?: string) {
  const data = await safeJsonFetch(`${SOUND_CLOUD_API}/resolve`, {
    params: { url: sourceUrl, client_id: clientId },
    token,
  });

  if (!data || !data.id) {
    throw new Error(`Could not resolve user for ${sourceUrl}.`);
  }

  return data.id as string | number;
}

export function normalizeCollection(data: any): any[] {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.collection)) return data.collection;
  if (Array.isArray(data.items)) return data.items;
  return [];
}

export async function fetchCollection(
  category: "likes" | "followings" | "playlists",
  userId: string | number,
  clientId: string,
  token?: string,
  offset = 0,
  limit = 200
) {
  const endpoints: Record<"likes" | "followings" | "playlists", string> = {
    likes: `/users/${userId}/likes`,
    followings: `/users/${userId}/followings`,
    playlists: `/users/${userId}/playlists`,
  };

  const data = await safeJsonFetch(`${SOUND_CLOUD_API}${endpoints[category]}`, {
    params: { client_id: clientId, limit, offset },
    token,
  });

  return normalizeCollection(data);
}
