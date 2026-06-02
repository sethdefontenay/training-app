"""Plan-ingestion agent boundary (Claude) + Gmail delivery boundary.

Both are mockable Protocols with real shells that raise until credentials are wired.
HARD RULE: the agent only PROPOSES; committing is a separate, human-gated step.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.config import get_settings
from app.integrations.health import IntegrationNotConfigured
from app.schemas.plan_ingest import ProposedPlan


class IngestionAgent(Protocol):
    async def extract(self, email_text: str, attachments: list[str]) -> ProposedPlan: ...


class ClaudeIngestionAgent:
    """Real agent shell. Uses Claude to parse email + .docx into a ProposedPlan.

    Carbs drive insulin dosing, so the real prompt is instructed to flag any value it
    cannot read confidently (into ProposedPlan.flagged_fields) rather than guess.
    """

    async def extract(self, email_text: str, attachments: list[str]) -> ProposedPlan:
        settings = get_settings()
        if not getattr(settings, "anthropic_api_key", None):
            raise IntegrationNotConfigured("Anthropic API key not configured")
        raise NotImplementedError  # pragma: no cover


@dataclass
class PlanEmail:
    text: str
    sender: str
    attachments: list[str] = field(default_factory=list)


class GmailProvider(Protocol):
    async def fetch_latest_plan_email(self) -> PlanEmail | None: ...


class GmailClient:
    """Real Gmail client shell — only surfaces the PT's plan emails; raises until wired."""

    async def fetch_latest_plan_email(self) -> PlanEmail | None:
        settings = get_settings()
        if not getattr(settings, "gmail_refresh_token", None):
            raise IntegrationNotConfigured("Gmail credentials not configured")
        raise NotImplementedError  # pragma: no cover
