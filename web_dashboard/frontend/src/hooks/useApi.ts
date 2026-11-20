import { useState, useEffect, useCallback, useRef } from "react";
import {
  createLogSocket,
  getJobStatus,
  getNovel,
  getNovels,
  getQualityDebt,
  getTensionInsights,
  searchKnowledge,
} from "../api/client";
import type {
  LogEntry,
  KnowledgeSearchResult,
  NovelListItem,
  NovelOverview,
  QualityDebtReport,
  TensionInsights,
} from "../types";

export function useNovelList() {
  const [novels, setNovels] = useState<NovelListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNovels = useCallback(async () => {
    try {
      setLoading(true);
      setNovels(await getNovels());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载作品失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNovels(); }, [fetchNovels]);
  return { novels, loading, error, refetch: fetchNovels };
}

export function useQualityDebt() {
  const [report, setReport] = useState<QualityDebtReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true);
      setReport(await getQualityDebt());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载质量债务失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReport(); }, [fetchReport]);
  return { report, loading, error, refetch: fetchReport };
}

export function useTensionInsights() {
  const [report, setReport] = useState<TensionInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true);
      setReport(await getTensionInsights());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载张力数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReport(); }, [fetchReport]);
  return { report, loading, error, refetch: fetchReport };
}

export function useKnowledgeSearch(query: string, backend = "lexical") {
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async () => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    try {
      setLoading(true);
      const data = await searchKnowledge(query, backend);
      setResults(data.results || []);
    } finally {
      setLoading(false);
    }
  }, [query, backend]);

  return { results, loading, search };
}

export function useNovel(platform: string, name: string) {
  const [novel, setNovel] = useState<NovelOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasLoaded = useRef(false);

  const fetchNovel = useCallback(async () => {
    if (!platform || !name) return;
    try {
      if (!hasLoaded.current) setLoading(true);
      setNovel(await getNovel(platform, name));
      hasLoaded.current = true;
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载作品详情失败");
    } finally {
      setLoading(false);
    }
  }, [platform, name]);

  useEffect(() => { fetchNovel(); }, [fetchNovel]);
  return { novel, loading, error, refetch: fetchNovel };
}

export function useJobLogs(platform: string, name: string, jobId: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<string>("pending");

  useEffect(() => {
    if (!jobId) return;

    const ws = createLogSocket();
    ws.onopen = () => {
      ws.send(JSON.stringify({ job_id: jobId }));
    };
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "log") {
        setLogs((prev) => [...prev, { timestamp: msg.timestamp, level: msg.level, message: msg.message }]);
      } else if (msg.type === "done") {
        setStatus(msg.status);
      }
    };
    ws.onerror = () => {
      // Fallback to polling
      const poll = setInterval(async () => {
        try {
          const data = await getJobStatus(platform, name, jobId);
          setLogs(data.logs || []);
          if (["completed", "failed", "error"].includes(data.status)) {
            setStatus(data.status);
            clearInterval(poll);
          }
        } catch {}
      }, 1000);
    };
    return () => ws.close();
  }, [jobId, platform, name]);

  return { logs, status };
}
