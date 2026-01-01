"""PDF generation endpoints for tailored resumes.

Provides live preview and download endpoints for Typst-rendered PDFs.
Integrates with CP-15 tailored resume assembly pipeline.
"""

import asyncio
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.routers.jobs import tailor_resume_for_job
from src.services.pdf_generator import TypstCompilationError, generate_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/generate", tags=["generate"])


@router.get(
    "/preview/{job_id}",
    summary="Live preview PDF (inline)",
    response_class=Response
)
async def preview_pdf(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Generate and return PDF for inline browser preview.

    This endpoint returns the PDF with `Content-Disposition: inline` to
    allow browsers to display it directly (e.g., in an iframe or new tab).

    **Workflow:**
    1. Fetch tailored resume from CP-15 assembler
    2. Generate PDF using Typst compiler
    3. Return PDF binary with inline disposition

    **Prerequisites:**
    - Job must be analyzed (POST /jobs/{job_id}/analyze)
    - Resume data must be available (auto-assembled on demand)

    Args:
        job_id: Job UUID
        db: Database session

    Returns:
        PDF binary stream with application/pdf content type

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Job not analyzed
        HTTPException 500: PDF generation failed
        HTTPException 504: Compilation timeout

    Performance Target:
        <2 seconds total (including CP-15 assembly + Typst compilation)
    """
    try:
        logger.info(f"Generating preview PDF for job {job_id}")

        # Step 1: Get tailored resume (calls CP-15 assembler)
        tailored_resume = await tailor_resume_for_job(job_id, db)

        # Step 2: Generate PDF
        pdf_bytes = await generate_pdf(tailored_resume)

        # Step 3: Return PDF with inline disposition
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=preview.pdf"
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions from tailor_resume_for_job
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF generation timed out (>5s). Template may be too complex."
        )
    except TypstCompilationError as e:
        logger.error(f"Typst compilation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF compilation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"PDF preview failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF preview generation failed: {str(e)}"
        )


@router.get(
    "/download/{job_id}",
    summary="Download PDF with clean filename",
    response_class=Response
)
async def download_pdf(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Generate and download PDF with a clean, descriptive filename.

    This endpoint returns the PDF with `Content-Disposition: attachment` to
    trigger a browser download with a clean filename:
    `FirstName_LastName_CompanyName_Resume.pdf`

    **Filename Format:**
    - Example: `John_Doe_Google_Resume.pdf`
    - Spaces replaced with underscores
    - Special characters removed

    **Workflow:**
    1. Fetch tailored resume from CP-15 assembler
    2. Generate PDF using Typst compiler
    3. Construct clean filename from resume metadata
    4. Return PDF with attachment disposition

    Args:
        job_id: Job UUID
        db: Database session

    Returns:
        PDF binary stream with attachment disposition

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Job not analyzed
        HTTPException 500: PDF generation failed
        HTTPException 504: Compilation timeout

    Note:
        Personal info (first/last name) uses placeholders until User model
        is implemented in CP-17. Current filename: "John_Doe_CompanyName_Resume.pdf"
    """
    try:
        logger.info(f"Generating download PDF for job {job_id}")

        # Step 1: Get tailored resume
        tailored_resume = await tailor_resume_for_job(job_id, db)

        # Step 2: Generate PDF
        pdf_bytes = await generate_pdf(tailored_resume)

        # Step 3: Construct clean filename
        # Format: FirstName_LastName_CompanyName_Resume.pdf
        # TODO: Extract first/last name from User model (CP-17)
        first_name = "John"  # Placeholder
        last_name = "Doe"   # Placeholder
        company_name = tailored_resume.company_name.replace(" ", "_")

        # Remove special characters from company name
        company_clean = re.sub(r'[^A-Za-z0-9_]', '', company_name)

        filename = f"{first_name}_{last_name}_{company_clean}_Resume.pdf"

        logger.info(f"Download filename: {filename}")

        # Step 4: Return PDF with attachment disposition
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF generation timed out (>5s). Template may be too complex."
        )
    except TypstCompilationError as e:
        logger.error(f"Typst compilation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF compilation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"PDF download failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF download generation failed: {str(e)}"
        )
