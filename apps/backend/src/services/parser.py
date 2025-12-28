"""Resume parsing service with Ollama integration.

This module provides the core resume parsing functionality using Llama 3 via Ollama
to extract structured data from raw resume text and persist it to the database.
"""

import asyncio
import json
import re
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import (
    BulletPoint,
    Education,
    Experience,
    Project,
    ProjectBulletPoint,
)
from src.schemas.resume import ParsedResume
from src.utils.date_parser import parse_resume_date


class OllamaClient:
    """Async client for Ollama API.

    Provides methods to interact with Ollama for text generation tasks.
    """

    def __init__(self, base_url: str | None = None):
        """Initialize Ollama client.

        Args:
            base_url: Ollama API base URL. Defaults to settings.ollama_base_url
        """
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = 60.0  # LLM calls can be slow for long resumes

    async def generate(self, prompt: str, model: str = "llama3") -> str:
        """Call Ollama generate endpoint for text completion.

        Args:
            prompt: Prompt for the model
            model: Model name (default: llama3)

        Returns:
            Generated text response from the model

        Raises:
            httpx.HTTPError: On API failure
            asyncio.TimeoutError: On timeout (60s)
        """
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "stream": False
                        },
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data.get("response", "")
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Ollama request timed out after {self.timeout}s"
            )
        except httpx.HTTPError as e:
            raise httpx.HTTPError(f"Ollama API error: {str(e)}")


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


async def extract_resume_structure(
    raw_text: str,
    ollama: OllamaClient
) -> ParsedResume:
    """Extract structured data from resume text using Llama 3.

    Uses a structured prompt to extract experiences, education, and projects
    in JSON format, then validates with Pydantic.

    Args:
        raw_text: Raw resume text
        ollama: Ollama client instance

    Returns:
        ParsedResume with extracted and validated data

    Raises:
        ValueError: On extraction or validation failure
        asyncio.TimeoutError: If Ollama request times out
    """
    prompt = f"""You are a resume parser. Extract the following information from the resume below and return ONLY a JSON object (no additional text).

Required JSON structure:
{{
  "experiences": [
    {{
      "company_name": "Company Name",
      "role_title": "Job Title",
      "location": "City, State",
      "start_date": "Jan 2020",
      "end_date": "Dec 2022" or null,
      "is_current": false,
      "bullet_points": ["Achievement 1", "Achievement 2"]
    }}
  ],
  "education": [
    {{
      "institution": "University Name",
      "degree": "Bachelor of Science",
      "field_of_study": "Computer Science",
      "location": "City, State",
      "start_date": "Aug 2016",
      "end_date": "May 2020",
      "gpa": 3.8
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Brief description",
      "technologies": ["Python", "React"],
      "link": "https://github.com/user/repo",
      "bullet_points": ["Achievement 1"]
    }}
  ]
}}

Important rules:
1. For current positions, set "is_current": true and "end_date": null
2. Extract dates as written (e.g., "Jan 2020", "2020-01")
3. If GPA is not mentioned, omit the "gpa" field entirely
4. Preserve bullet points exactly as written (do not modify them)
5. Return ONLY the JSON object, no markdown formatting or commentary

Resume text:
{raw_text}
"""

    # Call Ollama to extract structure
    response = await ollama.generate(prompt)

    # Parse JSON from response
    try:
        data = extract_json_from_response(response)
        parsed = ParsedResume(**data)
        return parsed
    except (ValueError, ValidationError) as e:
        # Log the full response for debugging
        print(f"ERROR: Failed to parse Ollama response: {e}")
        print(f"Raw response: {response}")
        raise ValueError(
            f"Failed to extract structured data from resume: {str(e)}"
        )


async def persist_resume(
    parsed: ParsedResume,
    db: AsyncSession
) -> tuple[int, int, int, int]:
    """Persist parsed resume data to database.

    Creates Experience, Education, and Project records along with their
    related BulletPoint and ProjectBulletPoint records.

    Args:
        parsed: Parsed resume data
        db: Database session

    Returns:
        Tuple of (experience_count, education_count, project_count, total_bullets)

    Raises:
        ValueError: On date parsing errors
        SQLAlchemyError: On database errors
    """
    total_bullets = 0

    # Persist experiences with bullet points
    for exp_data in parsed.experiences:
        # Parse dates
        start_date = parse_resume_date(exp_data.start_date)
        end_date = (
            parse_resume_date(exp_data.end_date)
            if exp_data.end_date
            else None
        )

        # Create experience record
        experience = Experience(
            company_name=exp_data.company_name,
            role_title=exp_data.role_title,
            location=exp_data.location,
            start_date=start_date,
            end_date=end_date,
            is_current=exp_data.is_current
        )
        db.add(experience)
        await db.flush()  # Get ID for bullet points

        # Add bullet points
        for content in exp_data.bullet_points:
            bullet = BulletPoint(
                experience_id=experience.id,
                content=content
                # embedding_id remains None initially
            )
            db.add(bullet)
            total_bullets += 1

    # Persist education entries
    for edu_data in parsed.education:
        # Parse dates
        start_date = parse_resume_date(edu_data.start_date)
        end_date = (
            parse_resume_date(edu_data.end_date)
            if edu_data.end_date
            else None
        )

        education = Education(
            institution=edu_data.institution,
            degree=edu_data.degree,
            field_of_study=edu_data.field_of_study,
            location=edu_data.location,
            start_date=start_date,
            end_date=end_date,
            gpa=edu_data.gpa
        )
        db.add(education)

    # Persist projects with bullet points
    for proj_data in parsed.projects:
        project = Project(
            name=proj_data.name,
            description=proj_data.description,
            technologies=proj_data.technologies or [],
            link=proj_data.link
        )
        db.add(project)
        await db.flush()  # Get ID for bullet points

        # Add project bullet points
        for content in proj_data.bullet_points:
            bullet = ProjectBulletPoint(
                project_id=project.id,
                content=content
                # embedding_id remains None initially
            )
            db.add(bullet)
            total_bullets += 1

    # Commit all changes (relies on FastAPI dependency for rollback on error)
    await db.commit()

    return (
        len(parsed.experiences),
        len(parsed.education),
        len(parsed.projects),
        total_bullets
    )
