import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useNovelList } from "../../hooks/useApi";
import type { PipelineStage } from "../../types";
import { STAGE_COLORS } from "../../types";

export default function Sidebar() {
  const { novels, loading } = useNovelList();
  const location = useLocation();
  const [lengthFilter, setLengthFilter] = useState("全部");
  const [genreFilter, setGenreFilter] = useState("全部");

  const genreOptions = useMemo(
    () => Array.from(new Set(novels.flatMap((novel) => novel.genre_tags))).sort((a, b) => a.localeCompare(b, "zh-CN")),
    [novels],
  );
  const filteredNovels = useMemo(
    () => novels.filter((novel) => {
      const matchesLength = lengthFilter === "全部" || novel.length_type === lengthFilter;
      const matchesGenre = genreFilter === "全部" || novel.genre_tags.includes(genreFilter);
      return matchesLength && matchesGenre;
    }),
    [genreFilter, lengthFilter, novels],
  );

  // Extract current novel from URL
  const match = location.pathname.match(/\/novel\/([^/]+)\/(.+)/);
  const currentPlatform = match ? decodeURIComponent(match[1]) : "";
  const currentName = match ? decodeURIComponent(match[2]) : "";

  return (
    <aside className="sticky top-0 flex h-screen w-[278px] flex-shrink-0 flex-col overflow-hidden bg-[#202a25] text-[#f3f0e7]">
      <div className="border-b border-white/10 px-6 pb-6 pt-7">
        <Link to="/" className="group flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#c9563d] text-sm font-bold tracking-[0.2em] text-white shadow-lg shadow-[#c9563d]/20">NC</span>
          <span>
            <span className="block text-[11px] font-bold uppercase tracking-[0.22em] text-[#c9d4c8]">Narrative</span>
            <span className="display-serif block text-xl leading-none text-[#fffaf0] transition group-hover:text-[#edb59f]">小说创作 Pro Max</span>
          </span>
        </Link>
        <div className="mt-5 flex items-center justify-between text-[10px] uppercase tracking-[0.16em] text-[#94a99a]">
          <span>Editorial OS / 01</span>
          <span className="flex items-center gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-[#8fc59d]" /> Local</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mb-3 flex items-center justify-between px-2">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#8da193]">作品架</h3>
          <span className="text-[10px] text-[#6f8577]">{filteredNovels.length}/{novels.length}</span>
        </div>
        {!loading && novels.length > 0 && (
          <div className="mb-4 grid grid-cols-2 gap-2">
            <select
              aria-label="篇幅筛选"
              value={lengthFilter}
              onChange={(event) => setLengthFilter(event.target.value)}
              className="min-w-0 rounded-lg border border-white/10 bg-[#2a3931] px-2 py-2 text-[11px] text-[#d7e0d6] outline-none"
            >
              <option value="全部">全部篇幅</option>
              <option value="长篇">长篇</option>
              <option value="中篇">中篇</option>
              <option value="短篇">短篇</option>
              <option value="未分类">未分类</option>
            </select>
            <select
              aria-label="题材筛选"
              value={genreFilter}
              onChange={(event) => setGenreFilter(event.target.value)}
              className="min-w-0 rounded-lg border border-white/10 bg-[#2a3931] px-2 py-2 text-[11px] text-[#d7e0d6] outline-none"
            >
              <option value="全部">全部题材</option>
              {genreOptions.map((genre) => <option key={genre} value={genre}>{genre}</option>)}
            </select>
          </div>
        )}
        {loading ? (
          <p className="px-2 text-sm text-[#8da193]">正在整理稿件...</p>
        ) : filteredNovels.length === 0 ? (
          <p className="px-2 text-sm text-[#8da193]">还没有符合条件的作品</p>
        ) : (
          <div className="space-y-2">
            {filteredNovels.map((novel) => {
              const isActive = novel.platform === currentPlatform && novel.novel_name === currentName;
              return (
                <Link
                  key={`${novel.platform}/${novel.novel_name}`}
                  to={`/novel/${encodeURIComponent(novel.platform)}/${encodeURIComponent(novel.novel_name)}`}
                  className={`group block rounded-xl border px-3 py-3 transition ${
                    isActive ? "border-[#c9563d]/50 bg-[#31463c] text-white" : "border-transparent text-[#bdc9bd] hover:border-white/10 hover:bg-white/5"
                  }`}
                >
                  <div className="truncate text-sm font-medium">{novel.novel_name}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-[#c9563d]/15 px-1.5 py-0.5 text-[10px] text-[#edb59f]">{novel.length_type}</span>
                    {novel.genre_tags.slice(0, 2).map((genre) => (
                      <span key={genre} className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-[#b8c8b8]">{genre}</span>
                    ))}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span
                      className="inline-block h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: STAGE_COLORS[novel.current_stage as PipelineStage] || "#8da193" }}
                    />
                    <span className="truncate text-[10px] tracking-wide text-[#8da193]">
                      {novel.platform} · {novel.chapters_written}章 · {novel.current_stage}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {currentPlatform && currentName && (
        <nav className="border-t border-white/10 px-4 py-5">
          <h3 className="mb-3 px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-[#8da193]">当前作品</h3>
          <div className="space-y-1">
            {[
              { path: "", label: "工作台", icon: "✦" },
            ].map(({ path, label, icon }) => (
              <Link
                key={path}
                to={`/novel/${encodeURIComponent(currentPlatform)}/${encodeURIComponent(currentName)}${path}`}
                className="block rounded-lg px-3 py-2 text-sm text-[#bdc9bd] transition hover:bg-white/5 hover:text-white"
              >
                <span className="mr-3 text-[#c9563d]">{icon}</span>{label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </aside>
  );
}
