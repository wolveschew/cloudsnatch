export type Category = "likes" | "followings" | "playlists";

export type ExportRecord = {
  id: string | number;
  raw: any;
  sourceUrl?: string;
  createdAt?: string;
};

export type FailedItem = {
  category: Category;
  id: string | number;
  kind: string;
  error: string;
  retryable: boolean;
  payload?: any;
  timestamp: string;
};

export type State = {
  version: number;
  sourceUrl?: string;
  targetUrl?: string;
  sourceUserId?: string | number;
  targetUserId?: string | number;
  completed: Partial<Record<Category, boolean>>;
  exports: Partial<Record<Category, ExportRecord[]>>;
  lastOffsets: Partial<Record<Category, number>>;
  lastRun: string;
};
