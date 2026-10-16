"""Load and validate run configuration (YAML). Invariant: budgets are positive and capped."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModelRoleConfig(BaseModel):
    name: str
    temperature: float = 0.0


class LLMProviderConfig(BaseModel):
    provider: Literal["openrouter", "mock"] = "mock"
    base_url: str = "https://openrouter.ai/api/v1"


class BudgetConfig(BaseModel):
    total_dollars: float = Field(gt=0)
    per_round_dollars: float = Field(gt=0)
    per_candidate_dollars: float = Field(gt=0)
    warn_at_fraction: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def caps_within_total(self) -> BudgetConfig:
        if self.per_round_dollars > self.total_dollars:
            raise ValueError("per_round_dollars must not exceed total_dollars")
        if self.per_candidate_dollars > self.total_dollars:
            raise ValueError("per_candidate_dollars must not exceed total_dollars")
        return self


class LoopConfig(BaseModel):
    rounds: int = Field(ge=1)
    opt_batch: int = Field(ge=1)
    candidates_per_round: int = Field(ge=1)
    val_tasks_per_round: int = Field(ge=1)
    seeds: list[int] = Field(min_length=1)
    patience: int = Field(ge=1)
    champion_top_k: int = Field(ge=1)
    # False skips ChampionAudit. Use for live debugging so `select` stays unread.
    champion_audit: bool = True


class StrategyRef(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str


class LeakageLinterConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "literal_overlap"
    min_literal_len: int = 12


class StrategiesConfig(BaseModel):
    surface: str = "S3"
    diagnoser: StrategyRef
    proposer: StrategyRef
    gate: StrategyRef
    search: StrategyRef
    leakage_linter: LeakageLinterConfig | None = None


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    splits_manifest: str | None = None
    domain: str | None = None
    tau2_root: str | None = None
    use_live_tau2: bool = False


class RunConfig(BaseModel):
    """Top-level config for `rsi-harness run`."""

    run_id: str
    workdir: Path = Path("./runs")
    seed: int = 7
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    models: dict[str, ModelRoleConfig]
    budget: BudgetConfig
    loop: LoopConfig
    strategies: StrategiesConfig
    benchmark: BenchmarkConfig

    @field_validator("workdir", mode="before")
    @classmethod
    def pathify(cls, v: str | Path) -> Path:
        return Path(v)


def load_run_config(path: Path) -> RunConfig:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return RunConfig.model_validate(raw)
