import type {
  ChapterCard,
  ChapterResponse,
  EntityGraph,
  HealthResponse,
  JobStatus,
  KnowledgeSearchResponse,
  MemoryStats,
  NovelListItem,
  NovelOverview,
  PipelineJobCreated,
  QualityDebtReport,
  SaveChapterResponse,
  StageAssetContent,
  TensionInsights,
} from "../types";

const API_BASE = "/api";

function getErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return fallback;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(getErrorMessage(payload, `HTTP ${res.status} ${res.statusText}`));
  }
  return res.json();
}

function novelPath(platform: string, name: string): string {
  return `/novels/${encodeURIComponent(platform)}/${encodeURIComponent(name)}`;
}

export const createLogSocket = (): WebSocket => {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(`${protocol}//${window.location.host}/ws/logs`);
};

export const getNovels = (): Promise<NovelListItem[]> => request("/novels");
export const getNovel = (platform: string, name: string) =>
  request<NovelOverview>(novelPath(platform, name));
export const getNovelState = (platform: string, name: string) =>
  request<Record<string, unknown>>(`${novelPath(platform, name)}/state`);

export const getChapters = (platform: string, name: string) =>
  request<ChapterCard[]>(`${novelPath(platform, name)}/chapters`);
export const getChapter = (platform: string, name: string, num: number) =>
  request<ChapterResponse>(`${novelPath(platform, name)}/chapters/${num}`);
export const saveChapter = (platform: string, name: string, num: number, content: string) =>
  request<SaveChapterResponse>(`${novelPath(platform, name)}/chapters/${num}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
export const getChapterSummary = (platform: string, name: string, num: number) =>
  request<Record<string, unknown> | null>(`${novelPath(platform, name)}/chapters/${num}/summary`);

export const runPipeline = (platform: string, name: string, action: string, chapter?: number) =>
  request<PipelineJobCreated>(`${novelPath(platform, name)}/pipeline/${action}`, {
    method: "POST",
    body: JSON.stringify({ chapter }),
  });
export const getJobStatus = (platform: string, name: string, jobId: string) =>
  request<JobStatus>(`${novelPath(platform, name)}/pipeline/jobs/${encodeURIComponent(jobId)}`);
export const getJobs = (platform: string, name: string) =>
  request<JobStatus[]>(`${novelPath(platform, name)}/pipeline/jobs`);

export const getMemoryStats = (platform: string, name: string) =>
  request<MemoryStats>(`${novelPath(platform, name)}/memory/stats`);
export const queryMemory = (platform: string, name: string, type: string) => {
  const params = new URLSearchParams({ type });
  return request<Array<Record<string, unknown>>>(`${novelPath(platform, name)}/memory/query?${params}`);
};
export const getEntityGraph = (platform: string, name: string) =>
  request<EntityGraph>(`${novelPath(platform, name)}/memory/entity-graph`);

export const getStageAsset = (platform: string, name: string, assetPath: string) => {
  const encodedPath = assetPath.split("/").map((part) => encodeURIComponent(part)).join("/");
  return request<StageAssetContent>(`${novelPath(platform, name)}/assets/${encodedPath}`);
};

export const getQualityDebt = () => request<QualityDebtReport>("/insights/quality-debt");
export const getTensionInsights = () => request<TensionInsights>("/insights/tension");
export const searchKnowledge = (query: string, backend = "lexical", limit = 8) => {
  const params = new URLSearchParams({ q: query, backend, limit: String(limit) });
  return request<KnowledgeSearchResponse>(`/insights/knowledge-search?${params}`);
};

export const healthCheck = () => request<HealthResponse>("/health");
