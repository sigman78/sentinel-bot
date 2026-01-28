"""User profile structure and management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UserProfile:
    """Structured user profile with preferences and context.

    Stores persistent user information learned from conversations,
    enabling personalized responses and better context awareness.
    """

    # Basic identity
    name: str = "User"
    timezone: str | None = None  # e.g., "America/Los_Angeles", "UTC+8"
    language: str = "en"  # ISO 639-1 code

    # Communication preferences
    communication_style: str = "casual"  # casual, formal, technical
    response_length: str = "balanced"  # concise, balanced, detailed

    # Context and environment
    environment: str = "personal"  # personal, work, mobile
    context: str | None = None  # Free-form context string (legacy compatibility)

    # Preferences (flexible key-value storage)
    preferences: dict[str, Any] = field(default_factory=dict)
    # Examples: {"code_style": "functional", "notification_time": "morning"}

    # Interests and expertise
    interests: list[str] = field(default_factory=list)
    expertise_areas: list[str] = field(default_factory=list)
    learning_goals: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to dictionary for JSON storage."""
        return {
            "name": self.name,
            "timezone": self.timezone,
            "language": self.language,
            "communication_style": self.communication_style,
            "response_length": self.response_length,
            "environment": self.environment,
            "context": self.context,
            "preferences": self.preferences,
            "interests": self.interests,
            "expertise_areas": self.expertise_areas,
            "learning_goals": self.learning_goals,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        """Deserialize profile from dictionary."""
        # Handle datetime fields
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**data)

    def update_fields(self, **fields: Any) -> None:
        """Update profile fields and timestamp."""
        for key, value in fields.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()

    def add_interest(self, interest: str) -> None:
        """Add an interest if not already present."""
        if interest not in self.interests:
            self.interests.append(interest)
            self.updated_at = datetime.now()

    def add_expertise(self, area: str) -> None:
        """Add expertise area if not already present."""
        if area not in self.expertise_areas:
            self.expertise_areas.append(area)
            self.updated_at = datetime.now()

    def set_preference(self, key: str, value: Any) -> None:
        """Set a preference value."""
        self.preferences[key] = value
        self.updated_at = datetime.now()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a preference value with optional default."""
        return self.preferences.get(key, default)

    def to_prompt_context(self) -> str:
        """Format profile for injection into system prompts."""
        lines = [f"User: {self.name}"]

        if self.timezone:
            lines.append(f"Timezone: {self.timezone}")

        if self.environment != "personal":
            lines.append(f"Environment: {self.environment}")

        if self.communication_style != "casual":
            lines.append(f"Communication: {self.communication_style}")

        if self.interests:
            lines.append(f"Interests: {', '.join(self.interests)}")

        if self.expertise_areas:
            lines.append(f"Expertise: {', '.join(self.expertise_areas)}")

        if self.preferences:
            pref_items = [f"{k}={v}" for k, v in self.preferences.items()]
            lines.append(f"Preferences: {', '.join(pref_items)}")

        if self.context:
            lines.append(f"Context: {self.context}")

        return "\n".join(lines)
