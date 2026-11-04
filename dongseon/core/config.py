"""Application settings.

All relative paths are resolved against the repository root so that every entry point
(API server, CLI, tests) uses the same database and config files regardless of the
working directory.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a path relative to the repository root.

    Args:
        path: Absolute path, or a path relative to the repository root.

    Returns:
        The absolute path.
    """
    p = Path(path).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


class Settings(BaseSettings):
    """Settings loaded from environment variables and the repo-root ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: str = "data/dongseon.db"
    profile_path: str = "config/profile.yaml"
    defaults_path: str = "config/defaults.yaml"
    cities_dir: str = "config/cities"
    lock_dir: str = "data/locks"

    google_maps_server_key: str = ""
    vite_google_maps_js_key: str = ""
    vite_google_map_id: str = ""
    google_free_tier_warn_ratio: float = 0.8
    google_free_tier_stop_ratio: float = 1.0

    llm_model: str = ""
    llm_daily_token_limit: int = 500_000

    dongseon_port: int = 8100
    dongseon_dev_port: int = 8101

    @property
    def database_file(self) -> Path:
        """Absolute path of the SQLite database."""
        return resolve_repo_path(self.database_path)

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL of the SQLite database."""
        return f"sqlite:///{self.database_file}"

    @property
    def lock_path(self) -> Path:
        """Absolute directory for job lock files."""
        return resolve_repo_path(self.lock_dir)

    @property
    def profile_file(self) -> Path:
        """Absolute path of the personal profile YAML."""
        return resolve_repo_path(self.profile_path)

    @property
    def defaults_file(self) -> Path:
        """Absolute path of the shared defaults YAML (categories, dwell times, free-tier caps)."""
        return resolve_repo_path(self.defaults_path)

    @property
    def cities_path(self) -> Path:
        """Absolute directory holding per-city YAML files."""
        return resolve_repo_path(self.cities_dir)

    @property
    def configured_keys(self) -> dict[str, bool]:
        """Whether each external API key is set. Never exposes the values."""
        return {
            "google_maps_server": bool(self.google_maps_server_key),
            "google_maps_js": bool(self.vite_google_maps_js_key),
            "google_map_id": bool(self.vite_google_map_id),
        }


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
