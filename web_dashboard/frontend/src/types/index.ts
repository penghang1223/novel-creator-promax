// TypeScript types matching backend Pydantic models

export type PipelineStage = "创意" | "设定" | "大纲" | "细纲" | "正文" | "记忆更新" | "完结复盘";

export const STAGE_ORDER: PipelineStage[] = ["创意", "设定", "大纲", "细纲", "正文", "记忆更新", "完结复盘"];

export const STAGE_COLORS: Record<PipelineStage, string> = {
  "创意": "#8b5cf6",
  "设定": "#06b6d4",
  "大纲": "#3b82f6",
  "细纲": "#6366f1",
  "正文": "#f59e0b",
  "记忆更新": "#10b981",
  "完结复盘": "#ef4444",
};

export interface ChapterCard {
  chapter_number: number;
  title: string;
  stage: PipelineStage;
  rhythm_type: string | null;
  word_count: number | null;
  audit_passed: boolean | null;
  gate_passed: boolean | null;
  last_updated: string | null;
  sub_stages: Record<string, boolean>;
  foreshadowing_planted: string[];
  foreshadowing_resolved: string[];
}

export interface StageAsset {
  name: string;
  path: string;
  kind: string;
  updated_at: string | null;
}

export interface StageAssetContent {
  name: string;
  path: string;
  content: string;
  media_type: string;
}

export interface NovelListItem {
  novel_name: string;
  platform: string;
  chapters_written: number;
  current_stage: PipelineStage;
  length_type: "长篇" | "中篇" | "短篇" | "未分类";
  genre: string;
  genre_tags: string[];
  last_updated: string | null;
}

export interface NovelOverview {
  novel_name: string;
  platform: string;
  total_chapters_planned: number;
  chapters_written: number;
  current_stage: PipelineStage;
  chapters: ChapterCard[];
  stage_assets: Partial<Record<PipelineStage, StageAsset[]>>;
  protagonist: Record<string, any>;
  last_updated: string | null;
}

export interface ChapterContent {
  chapter_number: number;
  title: string;
  content: string;
  word_count: number;
}

export interface ChapterResponse {
  content: ChapterContent;
  summary: Record<string, unknown> | null;
}

export interface SaveChapterResponse {
  ok: boolean;
  word_count: number;
}

export interface ChapterMetrics {
  narrative_tension: number;
  emotional_change: number;
  foreshadowing_density: string;
  information_release: string;
  relationship_shift: string;
  knowledge_reference_count: number;
}

export interface LogEntry {
  timestamp: string;
  level: "info" | "warn" | "error" | "debug";
  message: string;
}

export interface JobStatus {
  id: string;
  action: string;
  status: "pending" | "running" | "completed" | "failed" | "error";
  exit_code: number | null;
  logs?: LogEntry[];
}

export interface PipelineJobCreated {
  job_id: string;
  action: string;
}

export interface MemoryStats {
  style_dna: number;
  character: number;
  plot: number;
  context: number;
  history: number;
  entity_graph?: {
    entities: number;
    edges: number;
  };
}

export interface TensionInsights {
  summary: {
    projects: number;
    chapters: number;
    points: number;
    average: number | null;
    peak: number | null;
    failed: number;
  };
  projects: Array<{
    novel_dir: string;
    chapters: Array<{
      chapter: number;
      values: number[];
      average: number | null;
      peak: number | null;
      status: string;
    }>;
  }>;
}

export interface KnowledgeSearchResult {
  path: string;
  title: string;
  score: number;
  matched_terms: number;
  snippet: string;
}

export interface KnowledgeSearchResponse {
  query: string;
  backend: string;
  results: KnowledgeSearchResult[];
}

export interface QualityDebtReport {
  schema_version: string;
  generated_at: string;
  summary: {
    projects: number;
    debts: number;
    high: number;
    medium: number;
    low: number;
  };
  projects: Array<Record<string, unknown>>;
  index?: Record<string, unknown>;
}

export interface EntityGraph {
  entities: Record<string, unknown>;
  edges: Array<Record<string, unknown>>;
  next_entity_id: number;
}

export interface HealthResponse {
  status: string;
  project_root: string;
}
