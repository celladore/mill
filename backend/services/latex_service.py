"""
LaTeX-to-PDF conversion service.
"""

import asyncio
import logging
import shutil
import subprocess
import uuid

import aiofiles
import aiofiles.os

from config import TEMP_DIR
from database import Database
from fastapi import HTTPException
from models import ConversionResult
from utils import auto_fix_latex, parse_latex_errors
from utils.security import sanitize_filename, validate_file_path
from services.artifact_storage_service import ArtifactStorageService
from services.artifact_record_service import ArtifactRecordService

logger = logging.getLogger(__name__)


class LatexService:
    @staticmethod
    async def process_latex_file(
        file_content: str,
        filename: str,
        auto_fix: bool = False,
        user_id: str | None = None,
    ) -> ConversionResult:
        """Process LaTeX file and convert to PDF"""
        conversion_id = str(uuid.uuid4())
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Create temporary directory for this conversion
        temp_dir = TEMP_DIR / conversion_id
        temp_dir.mkdir(exist_ok=True)

        try:
            # Apply auto-fix if requested
            fixed_content = None
            auto_fix_applied = False
            if auto_fix:
                file_content, auto_fix_applied = auto_fix_latex(file_content)
                if auto_fix_applied:
                    fixed_content = file_content

            # Sanitize filename to prevent path traversal
            safe_filename = sanitize_filename(filename)

            # Write LaTeX file (async I/O)
            tex_file = temp_dir / f"{safe_filename}.tex"
            # Validate path is within temp_dir
            validate_file_path(temp_dir, tex_file)
            # POC: Using aiofiles for async file I/O. For production, consider
            # buffering strategies for very large files.
            async with aiofiles.open(tex_file, "w", encoding="utf-8") as f:
                await f.write(file_content)

            # Run pdflatex
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", f"{filename}.tex"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if PDF was created
            pdf_file = temp_dir / f"{filename}.pdf"
            success = pdf_file.exists()

            # Parse errors and warnings (async I/O)
            errors = []
            warnings = []
            if result.returncode != 0 or not success:
                log_file = temp_dir / f"{filename}.log"
                if await aiofiles.os.path.exists(log_file):
                    async with aiofiles.open(
                        log_file, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        log_content = await f.read()
                    errors, warnings = parse_latex_errors(log_content)

                if not errors:
                    errors = [
                        f"LaTeX compilation failed with return code {result.returncode}"
                    ]
                    if result.stderr:
                        errors.append(result.stderr)

            artifact = None
            if success:
                artifact = await ArtifactStorageService.upload(
                    pdf_file,
                    conversion_id=conversion_id,
                    kind="document",
                    user_id=user_id,
                    content_type="application/pdf",
                )

            result_obj = ConversionResult(
                id=conversion_id,
                filename=filename,
                success=success,
                auto_fix_applied=auto_fix_applied,
                errors=errors,
                warnings=warnings,
                pdf_path=None,
                fixed_content=fixed_content if auto_fix_applied else None,
            )

            # Store result in database
            db = Database.get_db()
            persisted_result = result_obj.model_dump()
            if user_id:
                persisted_result["user_id"] = user_id
            if artifact:
                persisted_result.update(artifact.as_record())
            try:
                await db.conversions.insert_one(persisted_result)
            except asyncio.CancelledError:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.conversions, artifact, conversion_id, user_id,
                    f"cancelled document conversion {conversion_id}",
                )
                raise
            except Exception:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.conversions, artifact, conversion_id, user_id,
                    f"document conversion {conversion_id}",
                )
                raise

            return result_obj

        except subprocess.TimeoutExpired:
            logger.error(f"LaTeX compilation timed out for conversion {conversion_id}")
            raise HTTPException(
                status_code=408,
                detail="LaTeX compilation timed out. The document may be too complex or contain errors.",
            )
        except HTTPException:
            raise
        except ValueError as e:
            # Security-related errors (path traversal, invalid filename)
            logger.warning(
                f"Security validation error for conversion {conversion_id}: {str(e)}"
            )
            raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(
                f"File not found error for conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=404, detail="Required file not found during processing"
            )
        except PermissionError as e:
            logger.error(
                f"Permission error for conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="File system permission error")
        except Exception as e:
            # Log full exception for debugging
            logger.error(
                f"Unexpected error processing LaTeX for conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            # Don't expose internal error details to users
            raise HTTPException(
                status_code=500,
                detail="An error occurred during processing. Please try again or contact support.",
            )
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
