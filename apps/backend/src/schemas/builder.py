"""Builder state response schema."""

from pydantic import BaseModel

from src.schemas.education import EducationResponse
from src.schemas.experience import ExperienceResponse
from src.schemas.project import ProjectResponse
from src.schemas.skill import SkillResponse


class BuilderStateResponse(BaseModel):
    """Schema for full builder state (all resume data)."""

    experiences: list[ExperienceResponse]
    projects: list[ProjectResponse]
    skills: list[SkillResponse]
    education: list[EducationResponse]
