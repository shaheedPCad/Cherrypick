"""Cherrypicker service for intelligent bullet selection.

This module implements the core LLM-powered selection logic for CP-15.
It takes the match set from CP-14 (top 15 bullets + top 20 skills) and uses
Llama 3 to select exactly 3-5 most relevant, non-redundant bullets per
experience/project.

Key Features:
- Bullet grouping by source (experience or project)
- LLM prompt engineering for relevance + redundancy detection
- Graceful fallback to similarity-based selection on LLM failure
"""

import json
import logging
import re
from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel

from src.schemas.matchmaker import BulletMatch, MatchSet
from src.services.parser import OllamaClient

logger = logging.getLogger(__name__)


class CherrypickerResult(BaseModel):
    """Result of cherrypicker bullet selection.

    Maps source IDs (experience or project UUIDs) to lists of selected
    bullet IDs. These selections will be used by the assembler to fetch
    full database entities.
    """

    experience_selections: dict[UUID, list[UUID]]  # exp_id -> selected bullet_ids
    project_selections: dict[UUID, list[UUID]]  # proj_id -> selected bullet_ids


async def cherrypick_bullets(
    match_set: MatchSet, job_description: str, ollama: OllamaClient
) -> CherrypickerResult:
    """Cherry-pick 3-5 bullets per source using LLM.

    This is the main entry point for bullet selection. It groups bullets by
    source (experience/project), then uses the LLM to select 3-5 most relevant,
    non-redundant bullets for each source.

    Strategy:
    1. Group matched bullets by source_id (experience or project)
    2. For each source, present bullets to LLM with job context
    3. LLM selects 3-5 most relevant, non-redundant bullets
    4. Return selection map for assembler

    Args:
        match_set: MatchSet from matchmaker service (top 15 bullets)
        job_description: Raw job description for context
        ollama: Ollama client instance

    Returns:
        CherrypickerResult with selections per source

    Example:
        >>> match_set = await generate_match_set(job_id, db)
        >>> job = await get_job(job_id, db)
        >>> result = await cherrypick_bullets(match_set, job.raw_description, ollama)
        >>> # result.experience_selections = {exp_uuid: [bullet1, bullet2, bullet3]}
    """
    # Step 1: Group bullets by source
    experience_bullets = defaultdict(list)
    project_bullets = defaultdict(list)

    for bullet in match_set.matched_bullets:
        if bullet.source_type == "experience":
            experience_bullets[bullet.source_id].append(bullet)
        elif bullet.source_type == "project":
            project_bullets[bullet.source_id].append(bullet)
        else:
            logger.warning(
                f"Unknown source_type '{bullet.source_type}' for bullet {bullet.bullet_id}"
            )

    logger.info(
        f"Grouped bullets: {len(experience_bullets)} experiences, "
        f"{len(project_bullets)} projects"
    )

    # Step 2: Select bullets for each experience
    experience_selections = {}
    for source_id, bullets in experience_bullets.items():
        selected = await _select_bullets_for_source(
            bullets, job_description, "experience", ollama
        )
        experience_selections[source_id] = selected
        logger.info(f"Selected {len(selected)} bullets for experience {source_id}")

    # Step 3: Select bullets for each project
    project_selections = {}
    for source_id, bullets in project_bullets.items():
        selected = await _select_bullets_for_source(
            bullets, job_description, "project", ollama
        )
        project_selections[source_id] = selected
        logger.info(f"Selected {len(selected)} bullets for project {source_id}")

    return CherrypickerResult(
        experience_selections=experience_selections, project_selections=project_selections
    )


async def _select_bullets_for_source(
    bullets: list[BulletMatch], job_description: str, source_type: str, ollama: OllamaClient
) -> list[UUID]:
    """Select 3-5 bullets for a single source using LLM.

    Uses a carefully crafted prompt to guide the LLM in selecting the most
    relevant bullets while avoiding redundancy. The prompt emphasizes:
    - Relevance to job description
    - Non-redundancy (different accomplishments)
    - Diversity of tasks/impact

    Fallback Strategy:
    If the LLM fails to return valid JSON or the correct count (3-5), we
    fallback to selecting the top 5 bullets by similarity score. This ensures
    the endpoint never fails due to LLM errors.

    Args:
        bullets: List of BulletMatch objects for this source
        job_description: Raw job description text
        source_type: "experience" or "project" (for logging/prompt)
        ollama: Ollama client

    Returns:
        List of 3-5 bullet UUIDs selected by LLM (or fallback)
    """
    # Build bullet list for prompt
    bullet_list = "\n".join(
        [
            f"{i+1}. [ID: {b.bullet_id}] {b.content} (score: {b.similarity_score:.2f})"
            for i, b in enumerate(bullets)
        ]
    )

    # Construct LLM prompt
    prompt = f"""You are a resume expert helping tailor a resume for a job application.

JOB DESCRIPTION:
{job_description}

AVAILABLE BULLETS for this {source_type.upper()}:
{bullet_list}

TASK:
Select 3-5 bullets that are:
1. MOST RELEVANT to the job description
2. NON-REDUNDANT (each bullet should describe a DIFFERENT accomplishment)
3. Highest impact for this specific role

CONSTRAINTS:
- You MUST select between 3 and 5 bullets (inclusive)
- NO duplicate or overlapping accomplishments
- Consider similarity scores but prioritize relevance and diversity

Return ONLY a JSON array of bullet IDs, like this:
["uuid1", "uuid2", "uuid3"]

Your selection:"""

    try:
        # Call LLM
        response = await ollama.generate(prompt)

        # Parse JSON array from response
        # The LLM might wrap the JSON in markdown code blocks or add extra text
        # Try to extract just the JSON array
        json_match = re.search(r"\[[\s\S]*?\]", response)
        if not json_match:
            raise ValueError("No JSON array found in LLM response")

        selected_ids = json.loads(json_match.group(0))

        # Validate response
        if not isinstance(selected_ids, list):
            raise ValueError("Response is not a list")

        if len(selected_ids) < 3 or len(selected_ids) > 5:
            logger.warning(
                f"LLM returned {len(selected_ids)} bullets for {source_type}, "
                f"expected 3-5. Using fallback strategy."
            )
            # Fallback: take top 5 by similarity
            sorted_bullets = sorted(bullets, key=lambda b: b.similarity_score, reverse=True)
            return [b.bullet_id for b in sorted_bullets[:5]]

        # Convert to UUIDs and validate they exist in bullets
        valid_bullet_ids = {b.bullet_id for b in bullets}
        result = []

        for id_str in selected_ids:
            try:
                bullet_id = UUID(id_str)
                if bullet_id in valid_bullet_ids:
                    result.append(bullet_id)
                else:
                    logger.warning(f"LLM selected invalid bullet ID: {bullet_id}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse bullet ID '{id_str}': {e}")

        # If we don't have 3-5 valid IDs, use fallback
        if len(result) < 3 or len(result) > 5:
            logger.warning(
                f"After validation, only {len(result)} valid bullets for {source_type}. "
                f"Using fallback."
            )
            sorted_bullets = sorted(bullets, key=lambda b: b.similarity_score, reverse=True)
            return [b.bullet_id for b in sorted_bullets[:5]]

        return result

    except Exception as e:
        logger.error(f"Failed to parse LLM selection for {source_type}: {e}")
        logger.error(f"Raw LLM response: {response[:500] if 'response' in locals() else 'N/A'}")

        # Fallback: take top 5 by similarity
        logger.info(f"Using fallback strategy (top 5 by similarity) for {source_type}")
        sorted_bullets = sorted(bullets, key=lambda b: b.similarity_score, reverse=True)
        return [b.bullet_id for b in sorted_bullets[:5]]
