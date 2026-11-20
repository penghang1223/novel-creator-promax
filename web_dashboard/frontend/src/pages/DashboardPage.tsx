import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useKnowledgeSearch, useNovelList, useQualityDebt, useTensionInsights } from "../hooks/useApi";

function formatDate() {
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());
}

export default function DashboardPage() {
  const { novels, loading, error, refetch } = useNovelList();
  const { report: debtReport } = useQualityDebt();
  const { report: tensionReport } = useTensionInsights();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchBackend, setSearchBackend] = useState("lexical");
  const { results: searchResults, loading: searchLoading, search } = useKnowledgeSearch(searchQuery, searchBackend);
  const navigate = useNavigate();
  const featured = novels[0];
  const progress = featured?.chapters_written && featured.chapters_written > 0
    ? Math.min(100, Math.round((featured.chapters_written / Math.max(featured.chapters_written, 12)) * 100))
    : 0;
  const tensionValues = tensionReport?.projects.flatMap((project) => project.chapters.flatMap((chapter) => chapter.values)).slice(-36) || [];
  const totalDebts = debtReport?.summary?.debts ?? 0;
  const highDebts = debtReport?.summary?.high ?? 0;

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-[#777b72]">正在打开编辑部...</div>;
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-[#202521]">
        <p className="display-serif text-2xl">工作台暂时没有回应</p>
        <p className="text-sm text-[#777b72]">{error}</p>
        <button onClick={refetch} className="rounded-full bg-[#29443a] px-5 py-2 text-sm text-white">重新连接</button>
      </div>
    );
  }

  return (
    <div className="paper-grid min-h-screen px-5 py-6 text-[#202521] md:px-9 md:py-8">
      <header className="reveal mx-auto flex max-w-[1420px] items-end justify-between border-b border-black/10 pb-6">
        <div>
          <p className="eyebrow">{formatDate()} · writing room</p>
          <h1 className="display-serif mt-2 text-4xl leading-none tracking-tight text-[#202521] md:text-5xl">写作现场</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[#777b72]">把今天要推进的故事，放在手边。这里是你的章节、人物、伏笔和审稿状态的共同桌面。</p>
        </div>
        <button onClick={refetch} className="hidden rounded-full border border-black/15 px-4 py-2 text-xs font-semibold text-[#29443a] transition hover:border-[#29443a] hover:bg-white/50 md:block">同步作品架 ↻</button>
      </header>

      <main className="reveal reveal-delay-1 mx-auto mt-7 grid max-w-[1420px] grid-cols-1 gap-5 xl:grid-cols-[1.55fr_0.9fr_0.8fr]">
        <section className="workbench-card relative min-h-[340px] overflow-hidden bg-[#29443a] p-7 text-[#f6f1e6] transition duration-300 md:p-9 xl:col-span-2">
          <div className="absolute -right-20 -top-28 h-72 w-72 rounded-full border-[36px] border-[#c9563d]/20" />
          <div className="absolute bottom-0 right-0 h-32 w-2/3 bg-gradient-to-t from-black/15 to-transparent" />
          <div className="relative flex h-full flex-col justify-between">
            <div className="flex items-start justify-between gap-6">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#b7c7b6]">Featured manuscript / 当前主稿</p>
                <h2 className="display-serif mt-5 max-w-xl text-4xl leading-[1.08] md:text-5xl">{featured?.novel_name || "从一个新故事开始"}</h2>
                <p className="mt-4 text-sm text-[#b7c7b6]">{featured ? `${featured.platform} · ${featured.current_stage}阶段` : "还没有选中的作品"}</p>
              </div>
              <span className="rounded-full border border-[#b7c7b6]/30 px-3 py-1 text-[10px] uppercase tracking-[0.15em] text-[#d8e0d3]">{featured ? "In progress" : "Empty desk"}</span>
            </div>
            <div className="relative mt-12">
              <div className="mb-3 flex items-end justify-between">
                <div><span className="display-serif text-4xl">{featured?.chapters_written ?? 0}</span><span className="ml-2 text-xs text-[#b7c7b6]">章已写</span></div>
                <span className="text-xs text-[#b7c7b6]">创作进度 {progress}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/15"><div className="h-full rounded-full bg-[#e2a66d] transition-all" style={{ width: `${progress}%` }} /></div>
              <button onClick={() => featured && navigate(`/novel/${encodeURIComponent(featured.platform)}/${encodeURIComponent(featured.novel_name)}`)} className="mt-6 rounded-full bg-[#f4f1e9] px-5 py-2.5 text-sm font-semibold text-[#29443a] transition hover:bg-[#e2a66d]">进入作品台 <span className="ml-2">→</span></button>
            </div>
          </div>
        </section>

        <section className="workbench-card flex min-h-[340px] flex-col p-6 transition duration-300">
          <div className="flex items-center justify-between"><p className="eyebrow">Next move</p><span className="text-xl text-[#c9563d]">↗</span></div>
          <h2 className="display-serif mt-6 text-3xl leading-tight">今天，先把<br /><em className="not-italic text-[#c9563d]">下一场戏</em>写出来。</h2>
          <div className="mt-auto border-t border-black/10 pt-5">
            <div className="flex items-center gap-3"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e3d7bd] text-sm text-[#29443a]">01</span><div><p className="text-sm font-semibold">继续当前章节</p><p className="mt-1 text-xs text-[#777b72]">从上次断点接着走</p></div></div>
            <button onClick={() => featured && navigate(`/novel/${encodeURIComponent(featured.platform)}/${encodeURIComponent(featured.novel_name)}`)} className="mt-5 w-full rounded-xl border border-[#29443a]/20 py-2.5 text-xs font-bold text-[#29443a] transition hover:bg-[#29443a] hover:text-white">打开写作看板</button>
          </div>
        </section>

        <section className="workbench-card p-6 transition duration-300">
          <div className="flex items-center justify-between"><p className="eyebrow">Story pulse</p><span className="text-xs text-[#777b72]">最近回填</span></div>
          <div className="mt-6 flex items-end justify-between"><div><span className="display-serif text-4xl">{tensionReport?.summary.average ?? "—"}</span><span className="ml-2 text-xs text-[#777b72]">平均张力</span></div><span className="rounded-full bg-[#e5eadf] px-2 py-1 text-[10px] text-[#3f6453]">峰值 {tensionReport?.summary.peak ?? "—"}</span></div>
          <div className="mt-7 flex h-20 items-end gap-1 border-b border-black/10 pb-1">{tensionValues.map((value, index) => <span key={`${value}-${index}`} className="min-w-[3px] flex-1 rounded-t bg-[#c9563d]/75 transition hover:bg-[#29443a]" style={{ height: `${Math.max(10, value * 10)}%` }} />)}{!tensionValues.length && <p className="mb-3 text-xs text-[#777b72]">暂无曲线数据</p>}</div>
          <p className="mt-4 text-xs leading-5 text-[#777b72]">曲线用于观察叙事呼吸，不替代正式审稿。</p>
        </section>

        <section className="workbench-card p-6 transition duration-300">
          <div className="flex items-center justify-between"><p className="eyebrow">Review desk</p><span className="text-xl text-[#c79b48]">✳</span></div>
          <div className="mt-6 flex items-baseline gap-2"><span className="display-serif text-5xl">{totalDebts}</span><span className="text-sm text-[#777b72]">项待处理</span></div>
          <div className="mt-5 space-y-3 text-xs"><div className="flex justify-between border-b border-black/10 pb-3"><span className="text-[#777b72]">高优先级</span><strong className="text-[#c9563d]">{highDebts}</strong></div><div className="flex justify-between border-b border-black/10 pb-3"><span className="text-[#777b72]">中优先级</span><strong className="text-[#c79b48]">{debtReport?.summary?.medium ?? 0}</strong></div></div>
          <p className="mt-5 text-xs leading-5 text-[#777b72]">先处理会阻塞下一章的债务，再做风格润色。</p>
        </section>

        <section className="workbench-card p-6 transition duration-300 xl:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Knowledge shelf</p><h2 className="display-serif mt-2 text-2xl">从知识库召回一个答案</h2></div><select value={searchBackend} onChange={(event) => setSearchBackend(event.target.value)} className="rounded-full border border-black/15 bg-transparent px-3 py-2 text-xs text-[#29443a] outline-none"><option value="lexical">词法检索</option><option value="tfidf">TF-IDF 检索</option></select></div>
          <div className="mt-5 flex gap-2"><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") search(); }} placeholder="人物、场景、技法、平台规则..." className="min-w-0 flex-1 rounded-xl border border-black/15 bg-white/35 px-4 py-3 text-sm text-[#202521] outline-none placeholder:text-[#9a9b91] focus:border-[#29443a]" /><button onClick={search} className="rounded-xl bg-[#202521] px-5 py-3 text-xs font-bold text-[#f4f1e9] transition hover:bg-[#c9563d]">{searchLoading ? "检索中" : "检索"}</button></div>
          {searchResults.length > 0 && <div className="mt-5 grid gap-3 md:grid-cols-2">{searchResults.slice(0, 4).map((result) => <div key={result.path} className="rounded-xl border border-black/10 bg-white/30 p-3"><p className="truncate text-sm font-semibold text-[#29443a]">{result.title}</p><p className="mt-1 truncate text-[10px] text-[#9a9b91]">{result.path}</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-[#777b72]">{result.snippet}</p></div>)}</div>}
          {!searchResults.length && <p className="mt-5 text-xs text-[#9a9b91]">输入关键词，快速召回写作规则、技法和项目经验。</p>}
        </section>
      </main>

      <section className="reveal reveal-delay-2 mx-auto mt-8 max-w-[1420px]">
        <div className="mb-4 flex items-end justify-between"><div><p className="eyebrow">Your manuscripts</p><h2 className="display-serif mt-2 text-3xl">作品架</h2></div><span className="text-xs text-[#777b72]">{novels.length} 部作品</span></div>
        {novels.length === 0 ? <div className="workbench-card p-8 text-center text-sm text-[#777b72]">还没有作品，先从项目初始化开始。</div> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{novels.slice(0, 8).map((novel) => <Link key={`${novel.platform}/${novel.novel_name}`} to={`/novel/${encodeURIComponent(novel.platform)}/${encodeURIComponent(novel.novel_name)}`} className="workbench-card group p-5 transition duration-300"><div className="flex items-start justify-between gap-3"><span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9a9b91]">{novel.platform}</span><span className="text-lg text-[#c9563d] transition group-hover:translate-x-1">↗</span></div><h3 className="display-serif mt-8 truncate text-xl text-[#29443a]">{novel.novel_name}</h3><div className="mt-4 flex items-center justify-between text-xs text-[#777b72]"><span>{novel.chapters_written} 章</span><span>{novel.current_stage}</span></div><div className="mt-3 h-1 rounded-full bg-[#d9d8ce]"><div className="h-full rounded-full bg-[#c9563d]" style={{ width: `${Math.min(100, novel.chapters_written * 5)}%` }} /></div></Link>)}</div>}
      </section>
    </div>
  );
}
