"""
Domain-level constants for Teams destinations.

Currently one accountId maps to exactly one destination (unique index on
accountId), but the schema/repository layer is written so this can be
extended to a one-to-many mapping later without a breaking change
(e.g. by adding a `destinations: list[...]` array and removing the unique
index in favor of a compound index).
"""

TEAMS_DESTINATIONS_COLLECTION = "teams_destinations"
