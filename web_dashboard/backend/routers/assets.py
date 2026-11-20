"""Read-only project asset preview routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from models.novel import StageAssetContent
from utils.paths import get_novel_dir

router = APIRouter(prefix="/api/novels/{platform}/{name:path}/assets", tags=["assets"])
TEXT_EXTENSIONS = frozenset({".canvas", ".csv", ".json", ".md", ".text", ".txt", ".toml", ".yaml", ".yml"})


@router.get("/{asset_path:path}", response_model=StageAssetContent)
def get_asset_content(platform: str, name: str, asset_path: str):
    try:
        novel_dir = get_novel_dir(platform, name).resolve()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = (novel_dir / asset_path).resolve()
    try:
        target.relative_to(novel_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法资料路径") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="资料不存在")
    if target.suffix.lower() not in TEXT_EXTENSIONS:
        raise HTTPException(status_code=415, detail="暂不支持预览此文件类型")

    try:
        content = target.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=415, detail="资料不是可预览的文本文件") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="读取资料失败") from exc

    media_type = "application/json" if target.suffix.lower() == ".json" else "text/plain"
    return StageAssetContent(
        name=target.name,
        path=target.relative_to(novel_dir).as_posix(),
        content=content,
        media_type=media_type,
    )
