"""Application settings loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for the Intelligent Observability & Event Watchdog.

    Values are loaded from environment variables (case-insensitive) or from a
    `.env` file in the project root.  Provide at minimum SUPABASE_DB_URL.
    """

    app_name: str = "Intelligent Observability & Event Watchdog"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    supabase_db_url: str  # maps to SUPABASE_DB_URL

    # ── Anomaly Detection — Tier 1: Hard Thresholds ───────────────────────────
    error_count_threshold: int = 10
    error_rate_threshold: float = 0.25
    latency_threshold_ms: float = 2000.0

    # ── Anomaly Detection — Tier 2: Z-Score ──────────────────────────────────
    zscore_threshold: float = 2.5
    volume_zscore_threshold: float = 3.0

    # ── Watchdog Scheduler ────────────────────────────────────────────────────
    watchdog_interval_seconds: int = 60
    metric_window_minutes: int = 5
    baseline_lookback_windows: int = 60

    # ── Anomaly Detection — Tier 3: IsolationForest ───────────────────────────
    isolation_forest_min_samples: int = 20

    # ── Streamlit Dashboard ──────────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"

    # ── Testing ──────────────────────────────────────────────────────────────
    test_database_url: str = "sqlite:///./test_watchdog.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
