/** API shapes. The backend owns every calculation; these are display contracts only. */
export type Status = 'ok' | 'watch' | 'risk' | 'none';
export type CoreId = 'observatory' | 'climate' | 'economy' | 'lab';

export interface Destination {
  id: string; name: string; region: string; country: string; latitude: number | null; longitude: number | null;
  area_km2: number | null; description: string; is_pilot: boolean; attributes: Record<string, unknown>;
}

export interface Settings {
  theme: 'dark' | 'light'; units: string; date_format: string; currency: string; default_range_months: number;
  onboarding_complete: boolean; port: number; data_dir: string; effective: { port: number; data_dir: string };
}

export interface Meta {
  product: string; name: string; version: string; mode: string; network: string; demo_policy: string;
  settings: Settings; data_extent: { first_period: string | null; last_period: string | null };
  datasets: number; demo_datasets: number; cores: { id: CoreId; num: string; name: string }[]; information_chain: string[];
}

export interface Kpi {
  id: string; label: string; core: CoreId; unit: string; description: string; decimals: number; value: number | null;
  status: Status; change_pct: number | null; spark: number[]; empty: boolean; confidence: string | null; timestamp: string | null;
  period_label: string | null; source: { dataset_id: string; name: string; version: number; is_demo: boolean; quality_score: number | null } | null;
}

export interface Summary {
  destination_id: string; kpis: Kpi[]; has_demo: boolean; has_data: boolean;
  extent: { first_period: string | null; last_period: string | null };
  counts: { datasets: number; demo_datasets: number; warnings_active: number; incidents_open: number; readiness_pct: number | null;
    assets: number; projects: number; runs: number; mean_quality: number | null };
}

export interface VariableDef { name: string; label: string; unit: string; type: string; min: number | null; max: number | null; required: boolean; description: string; aliases: string[] }

export interface DatasetKind { kind: string; label: string; core: CoreId; frequency: string; description: string; variables: VariableDef[] }

export interface Quality {
  observations: number; periods: number; first_period: string | null; last_period: string | null; period_gaps: string[]; n_gaps: number;
  variables_defined: string[]; variables_observed: string[]; missing_required: string[]; flags: Record<string, number>;
  range_violations: number; completeness_pct: number; quality_score: number; level: string; checked_at: string;
}

export interface Dataset {
  id: string; destination_id: string; kind: string; kind_label: string; name: string; version: number; status: 'draft' | 'validated' | 'archived';
  frequency: string; quality_score: number | null; quality: Partial<Quality>; variable_defs: VariableDef[]; provenance: Record<string, unknown>;
  is_demo: boolean; created_at: string; updated_at: string; observations?: number; first_period?: string | null; last_period?: string | null;
  imports?: { id: string; file_name: string; file_hash: string; layout: string; inserted: number; updated: number; unchanged: number; skipped: number; created_at: string }[];
  versions?: { id: string; version: number; status: string }[];
}

export interface Observation { period: string; variable: string; value: number | null; unit: string; quality_flag: string }
export interface SeriesPoint { period: string; value: number; flag?: string }
export interface Series { variable: string; label: string; unit: string; points: SeriesPoint[] }

export interface Param { name: string; label: string; unit: string; description: string; type: string; default: unknown; min: number | null; max: number | null; required: boolean; source?: { kind: string; variable: string; aggregation: string } }
export interface Reference { key: string; citation: string; bibtex: string; url: string; doi: string }
export interface Method {
  id: string; version: string; name: string; category: string; core: CoreId; kind: 'calculation' | 'forecast'; summary: string;
  inputs: Param[]; outputs: { name: string; label: string; unit: string; description: string }[]; formula: string; method: string;
  references: Reference[]; weights: Record<string, number>; limitations: string[]; screening: boolean; label: string;
  known_cases: { inputs: Record<string, unknown>; expected: Record<string, unknown>; note: string }[]; changelog: string[]; enabled: boolean; markdown?: string;
}

export interface Provenance {
  result: Record<string, unknown>; inputs: Record<string, unknown>; parameters: Record<string, unknown>;
  method: { id: string; version: string; name: string; formula: string; screening: boolean; references: string[] };
  data: { dataset_id: string | null; dataset_version: number | null; dataset_hash: string | null; input_sources: Record<string, InputSource>; is_demo: boolean };
  quality: { score?: number | null; level?: string; completeness_pct?: number; last_file_hash?: string };
  software_version: string; timestamp: string; run_id: string; status: string;
}
export interface InputSource { dataset_id: string; dataset_version: number; variable: string; aggregation: string; periods: string[]; n: number; is_demo: boolean }

export interface Run {
  id: string; kind: 'calculation' | 'forecast' | 'model'; method_id: string; method_version: string; method_name: string;
  destination_id: string | null; dataset_id: string | null; dataset_version: number | null; dataset_hash: string | null;
  status: 'success' | 'failed'; error: string | null; label: string; is_demo: boolean; software_version: string; rerun_of: string | null;
  created_at: string; screening: boolean; current_method_version: string | null; headline?: string;
  inputs?: Record<string, unknown>; parameters?: Record<string, unknown>; outputs?: Record<string, unknown>;
  data_quality?: Record<string, unknown>; method?: Record<string, unknown>; provenance?: Provenance;
  history?: SeriesPoint[]; reproduced?: boolean; method_version_changed?: boolean;
}

export interface ForecastPoint { period: string; value: number; lo: number; hi: number }
export interface Backtest { mae: number | null; rmse: number | null; mape_pct: number | null; mase: number | null; n: number; holdout: number; predicted: number[]; actual: number[] }

export interface ModelPkg {
  id: string; version: string; name: string; task: string; description: string; framework: string; source_repo: string; source_ref: string;
  license: string; training_data: string; inputs: { name: string; label?: string; type: string; unit?: string; min?: number; max?: number; required?: boolean }[];
  outputs: { name: string; label?: string; unit?: string }[]; status: 'enabled' | 'disabled'; is_demo: boolean; evaluation: Record<string, unknown>;
  requirements_txt: string; installed_at: string;
}

export interface Scenario { id: string; name: string; notes: string; destination_id: string; run_id: string; created_at: string; run: Run | null }

export interface GisLayer { id: string; name: string; category: string; destination_id: string | null; source: string; color: string; visible: boolean; is_demo: boolean; features: number; geojson?: GeoJSON }
export interface GeoJSON { type: string; features: { type: string; properties: Record<string, unknown>; geometry: { type: string; coordinates: unknown } | null }[] }

export type Row = Record<string, unknown> & { id: string };

export interface ImportIssue { level: 'error' | 'warning'; row: number | null; column: string | null; code: string; message: string }
export interface Mapping {
  layout: 'long' | 'wide'; period_column: string | null; variable_column: string | null; value_column: string | null;
  unit_column: string | null; flag_column: string | null; columns: Record<string, string | null>; decimal: string; date_format: string;
  create_variables?: boolean;
}
export interface Detection {
  token: string; file_name: string; size: number; file_hash: string; format: string; encoding: string; delimiter: string; has_header: boolean;
  columns: string[]; n_rows: number; preview: string[][]; suggested_mapping: Mapping;
}
export interface ValidationReport {
  rows_total: number; valid_cells: number; errors: number; warnings: number; will_insert: number; will_update: number; unchanged: number;
  new_variables: VariableDef[]; issues: ImportIssue[]; issues_truncated: boolean; dataset_id: string; file_name: string; archived: boolean;
  already_imported: string | null;
  preview_observations: (Observation & { line: number; action: string; previous?: number })[];
}
export interface CommitResult { status: 'committed' | 'duplicate'; import_id: string; file_hash: string; inserted: number; updated: number; unchanged: number; skipped?: number; message?: string; quality?: Quality }
