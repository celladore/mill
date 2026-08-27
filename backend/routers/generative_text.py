"""Dark API lane for Sluice-backed Generate and Rewrite transformations."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from auth import get_current_user
from models import GenerativeTextRequest, GenerativeTextResult
from services.artifact_storage_service import ArtifactStorageService
from services.generative_text_service import GenerativeTextService

router = APIRouter(prefix="/api")


@router.post("/generate-text", response_model=GenerativeTextResult)
async def generate_text(
    body: GenerativeTextRequest,
    request: Request,
    user=Depends(get_current_user),
):
    return await GenerativeTextService.transform(
        body, user.id, request.headers.get("X-Request-ID")
    )


@router.get("/download-generated-text/{conversion_id}")
async def download_generated_text(conversion_id: str, user=Depends(get_current_user)):
    blob_name, media_type, record = await GenerativeTextService.get_output(
        conversion_id, user.id
    )
    return StreamingResponse(
        ArtifactStorageService.download(blob_name),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{record["filename"]}.{record["target_format"]}"'
            )
        },
    )
