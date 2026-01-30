"""Tests for UserProfile structure."""

from datetime import datetime

from sentinel.memory.profile import UserProfile


def test_user_profile_defaults():
    """Test default profile initialization."""
    profile = UserProfile()

    assert profile.name == "User"
    assert profile.language == "en"
    assert profile.communication_style == "casual"
    assert profile.environment == "personal"
    assert profile.preferences == {}
    assert profile.interests == []
    assert profile.expertise_areas == []


def test_user_profile_custom_values():
    """Test profile with custom values."""
    profile = UserProfile(
        name="Alice",
        timezone="UTC-8",
        language="en",
        communication_style="technical",
        environment="work",
    )

    assert profile.name == "Alice"
    assert profile.timezone == "UTC-8"
    assert profile.communication_style == "technical"
    assert profile.environment == "work"


def test_user_profile_serialization():
    """Test profile to_dict and from_dict."""
    original = UserProfile(
        name="Bob",
        timezone="UTC+1",
        interests=["AI", "Python"],
        preferences={"code_style": "functional"},
    )

    # Serialize
    data = original.to_dict()
    assert data["name"] == "Bob"
    assert data["timezone"] == "UTC+1"
    assert data["interests"] == ["AI", "Python"]
    assert data["preferences"]["code_style"] == "functional"

    # Deserialize
    restored = UserProfile.from_dict(data)
    assert restored.name == original.name
    assert restored.timezone == original.timezone
    assert restored.interests == original.interests
    assert restored.preferences == original.preferences


def test_user_profile_datetime_serialization():
    """Test datetime fields are properly serialized."""
    profile = UserProfile(name="Carol")
    data = profile.to_dict()

    # Should be ISO format strings
    assert isinstance(data["created_at"], str)
    assert isinstance(data["updated_at"], str)

    # Should deserialize back to datetime
    restored = UserProfile.from_dict(data)
    assert isinstance(restored.created_at, datetime)
    assert isinstance(restored.updated_at, datetime)


def test_user_profile_update_fields():
    """Test profile field updates."""
    profile = UserProfile(name="Dave")
    original_updated_at = profile.updated_at

    # Small delay to ensure timestamp changes
    import time

    time.sleep(0.01)

    profile.update_fields(
        communication_style="formal",
        environment="work",
    )

    assert profile.communication_style == "formal"
    assert profile.environment == "work"
    assert profile.updated_at > original_updated_at


def test_user_profile_add_interest():
    """Test adding interests."""
    profile = UserProfile()

    profile.add_interest("Machine Learning")
    assert "Machine Learning" in profile.interests

    # Adding duplicate should not duplicate
    profile.add_interest("Machine Learning")
    assert profile.interests.count("Machine Learning") == 1


def test_user_profile_add_expertise():
    """Test adding expertise areas."""
    profile = UserProfile()

    profile.add_expertise("Python")
    assert "Python" in profile.expertise_areas

    profile.add_expertise("Python")  # Duplicate
    assert profile.expertise_areas.count("Python") == 1


def test_user_profile_preferences():
    """Test preference get/set."""
    profile = UserProfile()

    profile.set_preference("theme", "dark")
    assert profile.get_preference("theme") == "dark"

    # Default value
    assert profile.get_preference("nonexistent", "default") == "default"


def test_user_profile_to_prompt_context():
    """Test formatting profile for prompt context."""
    profile = UserProfile(
        name="Eve",
        timezone="America/New_York",
        communication_style="formal",
        interests=["Security", "Privacy"],
        preferences={"code_review": "thorough"},
    )

    context = profile.to_prompt_context()

    assert "User: Eve" in context
    assert "Timezone: America/New_York" in context
    assert "Communication: formal" in context
    assert "Interests: Security, Privacy" in context
    assert "Preferences: code_review=thorough" in context


def test_user_profile_minimal_prompt_context():
    """Test minimal profile produces clean context."""
    profile = UserProfile(name="Frank")

    context = profile.to_prompt_context()

    # Should only show name for minimal profile
    assert "User: Frank" in context
    # Should not show defaults
    assert "casual" not in context  # Default communication style
    assert "personal" not in context  # Default environment
