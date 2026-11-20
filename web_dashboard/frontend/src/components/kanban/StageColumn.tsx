import type { ChapterCard, PipelineStage, StageAsset } from "../../types";
import ChapterCardComponent from "./ChapterCard";

interface Props {
  stage: PipelineStage;
  chapters: ChapterCard[];
  assets: StageAsset[];
  color: string;
  selectedChapter: ChapterCard | null;
  onSelect: (ch: ChapterCard) => void;
  onOpenAsset: (asset: StageAsset) => void;
}

export default function StageColumn({ stage, chapters, assets, color, selectedChapter, onSelect, onOpenAsset }: Props) {
  return (
    <div className="flex-shrink-0 w-64 flex flex-col bg-gray-900/50 rounded-lg">
      {/* Column header */}
      <div className="p-3 border-b border-gray-800" style={{ borderTopColor: color, borderTopWidth: 3 }}>
        <div className="flex items-center justify-between">
          <span className="font-semibold text-sm text-gray-200">{stage}</span>
          <div className="flex items-center gap-1.5">
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: color + "22", color }}
            >
              {chapters.length}
            </span>
            {assets.length > 0 && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-gray-400">
                {assets.length}份资料
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Chapter cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {assets.length > 0 && (
          <div className="mb-3 space-y-1.5">
            <div className="px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500">项目资料</div>
            {assets.map((asset) => (
              <button
                key={asset.path}
                type="button"
                onClick={() => onOpenAsset(asset)}
                className="block w-full rounded-md border border-gray-700/80 bg-gray-800/80 px-2.5 py-2 text-left transition hover:border-blue-500/60 hover:bg-gray-700/80"
              >
                <div className="truncate text-xs font-medium text-gray-200" title={asset.path}>{asset.name}</div>
                <div className="mt-1 truncate text-[10px] text-gray-500" title={asset.path}>{asset.path}</div>
              </button>
            ))}
          </div>
        )}
        {chapters.length === 0 && assets.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">暂无章节</div>
        ) : (
          chapters.map((ch) => (
            <ChapterCardComponent
              key={ch.chapter_number}
              chapter={ch}
              isSelected={selectedChapter?.chapter_number === ch.chapter_number}
              onClick={() => onSelect(ch)}
            />
          ))
        )}
      </div>
    </div>
  );
}
