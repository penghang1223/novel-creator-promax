import { useEffect, useState } from "react";
import { getStageAsset } from "../../api/client";
import type { StageAsset, StageAssetContent } from "../../types";

interface Props {
  platform: string;
  novelName: string;
  asset: StageAsset;
  onClose: () => void;
}

export default function StageAssetPreview({ platform, novelName, asset, onClose }: Props) {
  const [data, setData] = useState<StageAssetContent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    getStageAsset(platform, novelName, asset.path)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "读取资料失败");
      });
    return () => {
      active = false;
    };
  }, [asset.path, novelName, platform]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6" role="dialog" aria-modal="true" aria-label="资料预览">
      <div className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-gray-700 bg-gray-950 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-gray-100">{asset.name}</h3>
            <p className="mt-1 truncate text-xs text-gray-500">{asset.path}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭资料预览" className="ml-4 text-xl leading-none text-gray-500 hover:text-gray-200">×</button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-5">
          {error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : data ? (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-gray-300">{data.content}</pre>
          ) : (
            <p className="text-sm text-gray-500">正在读取资料...</p>
          )}
        </div>
      </div>
    </div>
  );
}
