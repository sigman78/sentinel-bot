"""
Memory module - hierarchical memory system.

Layers:
- working: Current session (volatile)
- episodic: Timestamped events/conversations
- semantic: Extracted facts
- profile: User model
- world: External environment model

Storage: SQLite + filesystem
"""
