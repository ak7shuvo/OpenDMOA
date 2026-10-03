"""Artifact loaders — whitelisted formats only."""
from __future__ import annotations

import json
from pathlib import Path

from .contract import PackageError


class LinearModel:
    """y = bias + Σ coef_i · x_i  (pure data, deterministic, safe)."""

    def __init__(self, artifact: dict):
        self.bias = float(artifact.get('bias', 0.0))
        self.coefficients = {k: float(v) for k, v in artifact.get('coefficients', {}).items()}
        self.clip_negative = bool(artifact.get('clip_negative', True))
        self.output = artifact.get('output', 'prediction')

    def predict(self, inputs: dict[str, float]) -> dict[str, float]:
        y = self.bias + sum(c * float(inputs.get(k, 0.0)) for k, c in self.coefficients.items())
        if self.clip_negative:
            y = max(y, 0.0)
        return {self.output: round(y, 4)}


def load_model(pkg_dir: str | Path, framework: str, artifact_name: str, allow_pickle: bool = False):
    path = Path(pkg_dir) / 'model' / artifact_name
    if framework == 'json-linear':
        return LinearModel(json.loads(path.read_text(encoding='utf-8')))
    if framework == 'sklearn-joblib':
        if not allow_pickle:
            raise PackageError('sklearn-joblib (pickle) artifacts are refused by default — unpickling executes code. '
                               'Set OPENDMO_ALLOW_PICKLE_MODELS=true only for fully trusted sources.')
        import joblib  # type: ignore  # optional, never auto-installed
        return joblib.load(path)
    raise PackageError(f'no loader for framework: {framework}')
