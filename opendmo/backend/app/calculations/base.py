"""Method registry primitives.

Every calculation in OpenDMO is a *registered, versioned, documented* pure
function. A ``Method`` declares everything a reviewer needs to reproduce a
result: id, version, inputs (with units and valid ranges), outputs, formula,
method narrative, references, weights, limitations and known-value
verification cases (which double as unit tests).

Methods never touch the database. The run service validates inputs, calls
``compute`` and persists an append-only provenance record.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


class CalculationError(ValueError):
    """Raised for invalid inputs or undefined results (e.g. division by zero)."""


@dataclass(frozen=True)
class Reference:
    key: str
    authors: str
    year: int
    title: str
    container: str = ''          # journal / book / series
    publisher: str = ''
    url: str = ''
    doi: str = ''
    entry_type: str = 'article'  # bibtex entry type

    def citation(self) -> str:
        parts = [f'{self.authors} ({self.year}). {self.title}.']
        if self.container:
            parts.append(f'{self.container}.')
        if self.publisher:
            parts.append(f'{self.publisher}.')
        if self.doi:
            parts.append(f'https://doi.org/{self.doi}')
        elif self.url:
            parts.append(self.url)
        return ' '.join(parts)

    def bibtex(self) -> str:
        fields = {'author': self.authors.replace(', &', ' and').replace(' & ', ' and '),
                  'title': '{' + self.title + '}', 'year': str(self.year)}
        if self.container:
            fields['journal' if self.entry_type == 'article' else 'booktitle' if self.entry_type == 'incollection' else 'series'] = self.container
        if self.publisher:
            fields['publisher'] = self.publisher
        if self.doi:
            fields['doi'] = self.doi
        if self.url:
            fields['url'] = self.url
        body = ',\n'.join(f'  {k} = {{{v}}}' for k, v in fields.items())
        return f'@{self.entry_type}{{{self.key},\n{body}\n}}'

    def as_dict(self) -> dict:
        return {'key': self.key, 'citation': self.citation(), 'bibtex': self.bibtex(),
                'url': self.url, 'doi': self.doi}


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    unit: str = ''
    description: str = ''
    type: str = 'float'          # float | int | factors | series
    default: Any = None
    min: float | None = None
    max: float | None = None
    required: bool = True
    # Optional binding used by "fill from dataset": (dataset kind, variable, aggregation)
    source: tuple[str, str, str] | None = None

    def as_dict(self) -> dict:
        d = {'name': self.name, 'label': self.label, 'unit': self.unit,
             'description': self.description, 'type': self.type, 'default': self.default,
             'min': self.min, 'max': self.max, 'required': self.required}
        if self.source:
            d['source'] = {'kind': self.source[0], 'variable': self.source[1], 'aggregation': self.source[2]}
        return d


@dataclass(frozen=True)
class Output:
    name: str
    label: str
    unit: str = ''
    description: str = ''

    def as_dict(self) -> dict:
        return {'name': self.name, 'label': self.label, 'unit': self.unit, 'description': self.description}


@dataclass(frozen=True)
class KnownCase:
    """A verification case: ``compute(inputs)`` must reproduce ``expected``."""
    inputs: dict
    expected: dict
    note: str = ''
    tol: float = 1e-6


@dataclass(frozen=True)
class Method:
    id: str
    version: str
    name: str
    category: str
    core: str                      # observatory | climate | economy | lab
    summary: str
    inputs: tuple[Param, ...]
    outputs: tuple[Output, ...]
    formula: str
    method: str
    compute: Callable[[dict], dict]
    references: tuple[Reference, ...] = ()
    weights: dict = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    screening: bool = False        # custom composite -> "screening indicator, not a certification"
    kind: str = 'calculation'      # calculation | forecast
    known_cases: tuple[KnownCase, ...] = ()
    changelog: tuple[str, ...] = ()

    def describe(self) -> dict:
        return {
            'id': self.id, 'version': self.version, 'name': self.name, 'category': self.category,
            'core': self.core, 'kind': self.kind, 'summary': self.summary,
            'inputs': [p.as_dict() for p in self.inputs],
            'outputs': [o.as_dict() for o in self.outputs],
            'formula': self.formula, 'method': self.method,
            'references': [r.as_dict() for r in self.references],
            'weights': self.weights, 'limitations': list(self.limitations),
            'screening': self.screening,
            'label': ('Screening indicator — not a certification or regulatory determination'
                      if self.screening else 'Established method'),
            'known_cases': [{'inputs': k.inputs, 'expected': k.expected, 'note': k.note}
                            for k in self.known_cases],
            'changelog': list(self.changelog),
        }

    def methodology_markdown(self) -> str:
        lines = [f'### {self.name} (`{self.id}` v{self.version})', '']
        if self.screening:
            lines += ['> **Screening indicator** — not a certification or regulatory determination.', '']
        lines += [self.summary, '', '**Formula**', '', '```', self.formula, '```', '', '**Method.** ' + self.method, '']
        lines.append('| Input | Unit | Range | Description |')
        lines.append('|---|---|---|---|')
        for p in self.inputs:
            rng = f"{'' if p.min is None else p.min}–{'' if p.max is None else p.max}"
            lines.append(f'| `{p.name}` {p.label} | {p.unit} | {rng} | {p.description} |')
        lines += ['', '| Output | Unit | Description |', '|---|---|---|']
        for o in self.outputs:
            lines.append(f'| `{o.name}` {o.label} | {o.unit} | {o.description} |')
        if self.weights:
            lines += ['', '**Weights:** ' + ', '.join(f'{k} = {v}' for k, v in self.weights.items())]
        if self.limitations:
            lines += ['', '**Limitations**', ''] + [f'- {x}' for x in self.limitations]
        if self.references:
            lines += ['', '**References**', ''] + [f'- {r.citation()}' for r in self.references]
        if self.known_cases:
            lines += ['', '**Verification cases** (enforced by unit tests)', '']
            for k in self.known_cases:
                lines.append(f'- inputs `{_compact(k.inputs)}` → `{_compact(k.expected)}`' + (f' — {k.note}' if k.note else ''))
        return '\n'.join(lines) + '\n'


def _compact(d: dict) -> str:
    return ', '.join(f'{k}={v}' for k, v in d.items())


# ---------------------------------------------------------------- helpers

def num(v: dict, key: str) -> float:
    try:
        x = float(v[key])
    except KeyError as exc:
        raise CalculationError(f'missing input: {key}') from exc
    except (TypeError, ValueError) as exc:
        raise CalculationError(f'input {key} is not numeric: {v.get(key)!r}') from exc
    if math.isnan(x) or math.isinf(x):
        raise CalculationError(f'input {key} is not finite')
    return x


def safe_div(a: float, b: float, what: str) -> float:
    if b == 0:
        raise CalculationError(f'{what}: denominator is zero')
    return a / b


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def band(value: float, cuts: list[tuple[float, str]], top: str) -> str:
    """Return the first label whose upper bound exceeds value; ``top`` otherwise."""
    for upper, label in cuts:
        if value < upper:
            return label
    return top


def r(x: float, n: int = 4) -> float:
    return round(x, n)
