"""Job description analysis service with Ollama integration.

This module provides functionality for parsing raw job descriptions using
Llama 3 via Ollama to extract structured data (responsibilities and skills).
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job
from src.schemas.job import ParsedJobDescription
from src.services.parser import OllamaClient

logger = logging.getLogger(__name__)


def extract_json_from_response(response: str) -> dict[str, Any]:
    """Extract JSON from Ollama response using multiple strategies.

    Llama 3 may wrap JSON in markdown code blocks or add commentary.
    This function tries multiple parsing strategies to extract valid JSON.

    Args:
        response: Raw Ollama response text

    Returns:
        Parsed JSON dictionary

    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # Strategy 1: Direct JSON parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    code_block_match = re.search(
        r'```(?:json)?\s*(\{.*?\})\s*```',
        response,
        re.DOTALL
    )
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first {...} block (handles commentary before/after)
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # If all strategies fail, raise descriptive error
    raise ValueError(
        f"Could not extract valid JSON from Ollama response. "
        f"Response preview: {response[:200]}"
    )


async def extract_job_structure(
    raw_description: str,
    ollama: OllamaClient
) -> ParsedJobDescription:
    """Extract structured data from job description using Llama 3.

    Uses a structured prompt to extract top responsibilities and hard skills
    in JSON format, then validates with Pydantic.

    Args:
        raw_description: Raw job posting text
        ollama: Ollama client instance

    Returns:
        ParsedJobDescription with extracted and validated data

    Raises:
        ValueError: On extraction or validation failure
        asyncio.TimeoutError: If Ollama request times out
    """
    prompt = f"""You are a job description analyzer. Extract structured information and return ONLY a JSON object.

CRITICAL INSTRUCTIONS:

1. **Top Responsibilities**: Extract 5-10 key TECHNICAL responsibilities from this job description.
   - Focus on technical duties, NOT soft skills like "leadership" or "communication"
   - Each responsibility should be a single, atomic statement
   - Examples: "Design and implement RESTful APIs", "Optimize database queries", "Deploy applications to AWS"

2. **Hard Skills**: Extract TECHNICAL/HARD skills only. NO soft skills.
   - Include: Programming languages, frameworks, tools, technologies, certifications
   - Exclude: Leadership, communication, teamwork, problem-solving, etc.
   - Examples of VALID skills: Python, React, Docker, PostgreSQL, AWS, Git
   - Examples of INVALID skills: Leadership, Communication, Teamwork

Required JSON structure:
{{
  "top_responsibilities": ["Responsibility 1", "Responsibility 2", ...],
  "hard_skills": ["Skill1", "Skill2", "Skill3", ...]
}}

Important rules:
1. Return ONLY the JSON object, no markdown formatting or commentary
2. Extract responsibilities as atomic statements (one accomplishment per item)
3. Filter out soft skills completely
4. If a skill appears with variations (e.g., "Python", "Python 3"), just use "Python"
5. Minimum 3 responsibilities, maximum 10
6. Minimum 3 hard skills

Job Description:
{raw_description}
"""

    # Call Ollama to extract structure
    response = await ollama.generate(prompt)

    # Parse JSON from response
    try:
        data = extract_json_from_response(response)
        parsed = ParsedJobDescription(**data)

        # Log extraction stats
        logger.info(
            f"Extracted {len(parsed.top_responsibilities)} responsibilities, "
            f"{len(parsed.hard_skills)} skills from job description"
        )

        return parsed
    except (ValueError, ValidationError) as e:
        # Log the full response for debugging
        logger.error(f"Failed to parse Ollama response: {e}")
        logger.error(f"Raw response: {response}")
        raise ValueError(
            f"Failed to extract structured data from job description: {str(e)}"
        )


async def analyze_job(
    job: Job,
    db: AsyncSession
) -> bool:
    """Analyze job description and populate parsed fields.

    Checks if job is already analyzed, then uses Llama 3 to extract
    responsibilities and skills. Updates Job model with parsed data.

    Args:
        job: Job ORM instance
        db: Database session

    Returns:
        True on success, False on failure

    Raises:
        ValueError: If extraction fails
        asyncio.TimeoutError: If Ollama times out
    """
    # Skip if already analyzed
    if job.is_analyzed:
        logger.info(f"Job {job.id} already analyzed, skipping")
        return True

    try:
        # Initialize Ollama client
        ollama = OllamaClient()

        # Extract job structure
        logger.info(f"Analyzing job {job.id}: {job.job_title} at {job.company_name}")
        parsed = await extract_job_structure(job.raw_description, ollama)

        # Update job with parsed data
        job.top_responsibilities = parsed.top_responsibilities
        job.hard_skills = parsed.hard_skills
        job.is_analyzed = True
        job.analyzed_at = datetime.now(timezone.utc)

        # Commit transaction
        await db.commit()
        await db.refresh(job)

        logger.info(
            f"Successfully analyzed job {job.id}: "
            f"{len(parsed.top_responsibilities)} responsibilities, "
            f"{len(parsed.hard_skills)} skills"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to analyze job {job.id}: {e}")
        # Rollback transaction on failure
        await db.rollback()
        raise
