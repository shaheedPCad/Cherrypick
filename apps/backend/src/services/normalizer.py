"""Bullet point normalization service.

This module provides functionality to transform resume bullet points into
professional "action-verb" format using Llama 3 via Ollama.
"""

from src.services.parser import OllamaClient


async def normalize_bullet_points(
    bullet_points: list[str],
    ollama: OllamaClient
) -> list[str]:
    """Normalize bullet points to action-verb format using Llama 3.

    Processes bullet points in batches to avoid token limits and transforms them
    to start with strong action verbs, removing first-person pronouns.

    Args:
        bullet_points: List of raw bullet points from resume
        ollama: Ollama client instance

    Returns:
        List of normalized bullet points (same length as input)

    Examples:
        Input: ["I worked on developing a new API"]
        Output: ["Developed new API for platform integration"]
    """
    if not bullet_points:
        return []

    # Process in batches to avoid token limits
    batch_size = 10
    normalized = []

    for i in range(0, len(bullet_points), batch_size):
        batch = bullet_points[i:i + batch_size]

        # Construct prompt for this batch
        bullets_text = '\n'.join(f"- {bp}" for bp in batch)
        prompt = f"""Transform the following resume bullet points to start with strong action verbs in past tense (or present tense if describing a current role).

Rules:
1. Start with action verb (e.g., "Developed", "Led", "Implemented", "Designed")
2. Remove first-person pronouns ("I", "my", "we", "our")
3. Be concise and impactful
4. Preserve technical details and metrics
5. Return one bullet per line, no numbering or dashes

Original bullets:
{bullets_text}

Normalized bullets:
"""

        # Call Ollama for normalization
        response = await ollama.generate(prompt)

        # Parse response (one bullet per line)
        normalized_batch = [
            line.strip().lstrip('-').lstrip('•').lstrip('*').strip()
            for line in response.split('\n')
            if line.strip()
            and not line.strip().startswith('#')
            and not line.strip().lower().startswith('normalized')
        ]

        # Validate we got the same number back
        if len(normalized_batch) != len(batch):
            # Fall back to original if normalization failed
            print(
                f"WARNING: Normalization count mismatch. "
                f"Expected {len(batch)}, got {len(normalized_batch)}. "
                f"Using original bullets for this batch."
            )
            normalized.extend(batch)
        else:
            normalized.extend(normalized_batch)

    return normalized
