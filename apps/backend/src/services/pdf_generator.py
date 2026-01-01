"""PDF generation service using Typst compiler.

This service converts TailoredResumeResponse Pydantic models to Typst-compatible
JSON and compiles them to PDF using the Typst CLI binary.

Performance Target: <2 seconds per PDF
Strategy: Async subprocess execution with efficient temp file management
"""

import asyncio
import json
import logging
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from src.schemas.tailored_resume import TailoredResumeResponse

logger = logging.getLogger(__name__)

# Constants
TYPST_BINARY = "/usr/local/bin/typst"
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "master.typ"
COMPILE_TIMEOUT = 5.0  # 5s max (generous buffer for 2s target)


class TypstCompilationError(Exception):
    """Raised when Typst compilation fails."""
    pass


def format_date_range(
    start_date: date,
    end_date: date | None,
    is_current: bool = False
) -> str:
    """Format date range for resume display.

    Converts Python date objects to human-readable format for resumes.

    Args:
        start_date: Start date of the experience/education
        end_date: End date (None if current)
        is_current: Whether this is an ongoing experience

    Returns:
        Formatted date range string (e.g., "Jan 2024 - Present")

    Examples:
        >>> format_date_range(date(2024, 1, 15), None, True)
        "Jan 2024 - Present"
        >>> format_date_range(date(2022, 6, 1), date(2023, 12, 31))
        "Jun 2022 - Dec 2023"
    """
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    start_str = f"{months[start_date.month - 1]} {start_date.year}"

    if is_current or end_date is None:
        end_str = "Present"
    else:
        end_str = f"{months[end_date.month - 1]} {end_date.year}"

    return f"{start_str} - {end_str}"


def convert_to_typst_data(resume: TailoredResumeResponse) -> dict[str, Any]:
    """Convert TailoredResumeResponse to Typst-compatible JSON structure.

    Transforms:
    - Date objects → formatted strings ("Jan 2024 - Present")
    - UUID objects → strings
    - Optional fields → None (handled by Typst template)
    - Nested Pydantic models → dicts

    Args:
        resume: Tailored resume response from assembler

    Returns:
        Dictionary ready for JSON serialization and Typst consumption

    Note:
        Personal info (candidate_name, email, phone, location) uses placeholders
        until User model is implemented in CP-17.
    """
    return {
        # Personal Info (TODO: Add to User model in CP-17)
        "candidate_name": "John Doe",  # Placeholder
        "email": "john.doe@example.com",  # Placeholder
        "phone": "+1 (555) 123-4567",  # Placeholder
        "location": "San Francisco, CA",  # Placeholder

        # Experiences
        "experiences": [
            {
                "company_name": exp.company_name,
                "role_title": exp.role_title,
                "location": exp.location,
                "dates": format_date_range(
                    exp.start_date,
                    exp.end_date,
                    exp.is_current
                ),
                "bullet_points": [
                    {"content": bullet.content}
                    for bullet in exp.bullet_points
                ]
            }
            for exp in resume.experiences
        ],

        # Projects
        "projects": [
            {
                "name": proj.name,
                "description": proj.description,
                "technologies": proj.technologies,
                "link": proj.link,  # None handled by template
                "bullet_points": [
                    {"content": bullet.content}
                    for bullet in proj.bullet_points
                ]
            }
            for proj in resume.projects
        ],

        # Skills (flat list)
        "skills": [
            {"name": skill.name}
            for skill in resume.skills
        ],

        # Education
        "education": [
            {
                "institution": edu.institution,
                "degree": edu.degree,
                "field_of_study": edu.field_of_study,
                "location": edu.location,
                "dates": format_date_range(edu.start_date, edu.end_date),
                "gpa": edu.gpa  # None handled by template
            }
            for edu in resume.education
        ]
    }


async def generate_pdf(resume: TailoredResumeResponse) -> bytes:
    """Generate PDF from tailored resume using Typst.

    Process:
    1. Convert resume to Typst-compatible JSON
    2. Write JSON to temp file
    3. Execute Typst compiler asynchronously
    4. Read PDF output
    5. Cleanup temp files

    Performance:
    - Async subprocess execution (non-blocking)
    - Temp files in /tmp (RAM-backed on most systems)
    - Timeout protection (5s max)

    Args:
        resume: Tailored resume data

    Returns:
        PDF binary content

    Raises:
        TypstCompilationError: If compilation fails
        asyncio.TimeoutError: If compilation exceeds 5s
        FileNotFoundError: If template not found

    Performance Target:
        ~500-1500ms total (well under 2s)
    """
    # Validate template exists
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Typst template not found: {TEMPLATE_PATH}"
        )

    logger.info(f"Generating PDF for job {resume.job_id}")
    start_time = asyncio.get_event_loop().time()

    # Create temp directory for this compilation
    with tempfile.TemporaryDirectory(prefix="typst_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Paths for temp files
        data_json_path = tmpdir_path / "data.json"
        output_pdf_path = tmpdir_path / "resume.pdf"

        try:
            # Step 1: Convert and write JSON data
            typst_data = convert_to_typst_data(resume)
            data_json_path.write_text(
                json.dumps(typst_data, indent=2),
                encoding="utf-8"
            )

            logger.debug(f"Wrote resume data to {data_json_path}")

            # Step 2: Execute Typst compiler
            # Command: typst compile master.typ resume.pdf --root <tmpdir>
            process = await asyncio.create_subprocess_exec(
                TYPST_BINARY,
                "compile",
                str(TEMPLATE_PATH),
                str(output_pdf_path),
                "--root", str(tmpdir_path),  # Set root for data.json lookup
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for compilation with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=COMPILE_TIMEOUT
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise asyncio.TimeoutError(
                    f"Typst compilation timed out after {COMPILE_TIMEOUT}s"
                )

            # Check exit code
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8")
                logger.error(f"Typst compilation failed: {error_msg}")
                raise TypstCompilationError(
                    f"Typst compilation failed (exit {process.returncode}): {error_msg}"
                )

            # Step 3: Read PDF output
            if not output_pdf_path.exists():
                raise TypstCompilationError(
                    "Typst compilation succeeded but PDF not found"
                )

            pdf_bytes = output_pdf_path.read_bytes()

            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(
                f"PDF generated successfully for job {resume.job_id} "
                f"in {elapsed:.2f}s ({len(pdf_bytes)} bytes)"
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {type(e).__name__}: {e}")
            raise

    # Temp directory auto-cleaned by context manager
