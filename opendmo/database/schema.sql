-- ============================================================================
-- OpenDMO v2.0 — reference DDL for PostgreSQL + PostGIS (optional engine).
--
-- Generated from backend/app/models.py (SQLAlchemy). The backend creates this
-- schema automatically on first start for either engine; this file is for
-- review and for hand-managed PostgreSQL instances.
--
--   docker compose up -d db
--   pip install -r backend/requirements-postgres.txt
--   OPENDMO_DATABASE_URL=postgresql+psycopg://opendmo:opendmo@localhost:5432/opendmo python run.py
--
-- Conventions: is_demo = TRUE marks synthetic seed-pack rows (always badged
-- DEMO in the UI). runs is append-only provenance.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE app_settings (
	key VARCHAR(64) NOT NULL, 
	value JSON, 
	PRIMARY KEY (key)
);


CREATE TABLE audit_log (
	id SERIAL NOT NULL, 
	ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	target VARCHAR(192) NOT NULL, 
	detail JSON NOT NULL, 
	actor VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_audit_log_ts ON audit_log (ts);
CREATE INDEX ix_audit_log_action ON audit_log (action);

CREATE TABLE briefs (
	id VARCHAR(48) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	destination_id VARCHAR(48), 
	run_ids JSON NOT NULL, 
	summary TEXT NOT NULL, 
	recommendations JSON NOT NULL, 
	markdown TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE destinations (
	id VARCHAR(48) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	region VARCHAR(160) NOT NULL, 
	country VARCHAR(80) NOT NULL, 
	latitude FLOAT, 
	longitude FLOAT, 
	area_km2 FLOAT, 
	description TEXT NOT NULL, 
	is_pilot BOOLEAN NOT NULL, 
	attributes JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE gis_layers (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	category VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48), 
	geojson JSON NOT NULL, 
	source VARCHAR(512) NOT NULL, 
	color VARCHAR(16) NOT NULL, 
	visible BOOLEAN NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_gis_layers_destination_id ON gis_layers (destination_id);

CREATE TABLE method_state (
	method_id VARCHAR(96) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (method_id)
);


CREATE TABLE models (
	id VARCHAR(64) NOT NULL, 
	version VARCHAR(32) NOT NULL, 
	name VARCHAR(192) NOT NULL, 
	task VARCHAR(64) NOT NULL, 
	description TEXT NOT NULL, 
	framework VARCHAR(64) NOT NULL, 
	source_repo VARCHAR(512) NOT NULL, 
	source_ref VARCHAR(128) NOT NULL, 
	license VARCHAR(64) NOT NULL, 
	training_data TEXT NOT NULL, 
	input_variables JSON NOT NULL, 
	output_variables JSON NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	package_path VARCHAR(1024) NOT NULL, 
	metadata_json JSON NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	installed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id, version)
);


CREATE TABLE publications (
	id VARCHAR(48) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	authors VARCHAR(512) NOT NULL, 
	pub_type VARCHAR(32) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	venue VARCHAR(255) NOT NULL, 
	due VARCHAR(10) NOT NULL, 
	brief_id VARCHAR(48), 
	notes TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE runs (
	id VARCHAR(48) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	method_id VARCHAR(96) NOT NULL, 
	method_version VARCHAR(32) NOT NULL, 
	destination_id VARCHAR(48), 
	dataset_id VARCHAR(96), 
	dataset_version INTEGER, 
	dataset_hash VARCHAR(64), 
	parameters JSON NOT NULL, 
	inputs JSON NOT NULL, 
	outputs JSON NOT NULL, 
	data_quality JSON NOT NULL, 
	method_snapshot JSON NOT NULL, 
	software_version VARCHAR(32) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	error TEXT, 
	label VARCHAR(192) NOT NULL, 
	rerun_of VARCHAR(48), 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_runs_destination_id ON runs (destination_id);
CREATE INDEX ix_runs_method_id ON runs (method_id);
CREATE INDEX ix_runs_kind ON runs (kind);
CREATE INDEX ix_runs_created_at ON runs (created_at);

CREATE TABLE scenarios (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	name VARCHAR(192) NOT NULL, 
	notes TEXT NOT NULL, 
	run_id VARCHAR(48) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_scenarios_destination_id ON scenarios (destination_id);

CREATE TABLE assets (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	name VARCHAR(192) NOT NULL, 
	asset_type VARCHAR(16) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	condition VARCHAR(16) NOT NULL, 
	threats JSON NOT NULL, 
	protection_status VARCHAR(96) NOT NULL, 
	latitude FLOAT, 
	longitude FLOAT, 
	gis_layer_id VARCHAR(64), 
	last_assessed VARCHAR(10) NOT NULL, 
	notes TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_assets_destination_id ON assets (destination_id);

CREATE TABLE datasets (
	id VARCHAR(96) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	kind VARCHAR(48) NOT NULL, 
	name VARCHAR(192) NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	frequency VARCHAR(16) NOT NULL, 
	quality_score FLOAT, 
	quality JSON NOT NULL, 
	variable_defs JSON NOT NULL, 
	provenance JSON NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (destination_id, kind, name, version), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_datasets_destination_id ON datasets (destination_id);
CREATE INDEX ix_datasets_kind ON datasets (kind);
CREATE INDEX ix_datasets_is_demo ON datasets (is_demo);

CREATE TABLE incidents (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	occurred_at VARCHAR(20) NOT NULL, 
	hazard VARCHAR(48) NOT NULL, 
	severity VARCHAR(16) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	response TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_incidents_destination_id ON incidents (destination_id);

CREATE TABLE infra_projects (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	name VARCHAR(192) NOT NULL, 
	category VARCHAR(48) NOT NULL, 
	stage VARCHAR(16) NOT NULL, 
	budget_bdt_m FLOAT, 
	start VARCHAR(10) NOT NULL, 
	"end" VARCHAR(10) NOT NULL, 
	notes TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_infra_projects_destination_id ON infra_projects (destination_id);

CREATE TABLE readiness_items (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	category VARCHAR(48) NOT NULL, 
	item VARCHAR(255) NOT NULL, 
	done BOOLEAN NOT NULL, 
	owner VARCHAR(96) NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_readiness_items_destination_id ON readiness_items (destination_id);

CREATE TABLE warnings (
	id VARCHAR(48) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	hazard VARCHAR(48) NOT NULL, 
	level VARCHAR(16) NOT NULL, 
	issued_at VARCHAR(20) NOT NULL, 
	valid_until VARCHAR(20) NOT NULL, 
	message TEXT NOT NULL, 
	source VARCHAR(192) NOT NULL, 
	active BOOLEAN NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES destinations (id)
);

CREATE INDEX ix_warnings_destination_id ON warnings (destination_id);

CREATE TABLE imports (
	id VARCHAR(48) NOT NULL, 
	dataset_id VARCHAR(96) NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_hash VARCHAR(64) NOT NULL, 
	file_format VARCHAR(16) NOT NULL, 
	layout VARCHAR(8) NOT NULL, 
	encoding VARCHAR(24) NOT NULL, 
	delimiter VARCHAR(4) NOT NULL, 
	mapping JSON NOT NULL, 
	rows_total INTEGER NOT NULL, 
	inserted INTEGER NOT NULL, 
	updated INTEGER NOT NULL, 
	unchanged INTEGER NOT NULL, 
	skipped INTEGER NOT NULL, 
	warnings JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (dataset_id, file_hash), 
	FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
);

CREATE INDEX ix_imports_dataset_id ON imports (dataset_id);
CREATE INDEX ix_imports_file_hash ON imports (file_hash);

CREATE TABLE observations (
	id SERIAL NOT NULL, 
	dataset_id VARCHAR(96) NOT NULL, 
	destination_id VARCHAR(48) NOT NULL, 
	period VARCHAR(16) NOT NULL, 
	variable VARCHAR(64) NOT NULL, 
	value FLOAT, 
	unit VARCHAR(32) NOT NULL, 
	quality_flag VARCHAR(16) NOT NULL, 
	import_id VARCHAR(48), 
	PRIMARY KEY (id), 
	UNIQUE (dataset_id, period, variable), 
	FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
);

CREATE INDEX ix_observations_destination_id ON observations (destination_id);
CREATE INDEX ix_observations_period ON observations (period);
CREATE INDEX ix_observations_variable ON observations (variable);
CREATE INDEX ix_observations_dataset_id ON observations (dataset_id);

-- ----------------------------------------------------------------------------
-- PostGIS view: every feature of every GIS layer as native geometry (EPSG:4326),
-- usable directly from QGIS. Layers are stored as GeoJSON for engine portability.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW gis_features AS
SELECT l.id AS layer_id, l.name AS layer_name, l.destination_id, l.is_demo,
       f.ordinality AS feature_no, f.value -> 'properties' AS properties,
       ST_SetSRID(ST_GeomFromGeoJSON((f.value -> 'geometry')::text), 4326) AS geom
FROM gis_layers l
CROSS JOIN LATERAL json_array_elements(l.geojson -> 'features') WITH ORDINALITY AS f(value, ordinality)
WHERE f.value -> 'geometry' IS NOT NULL AND json_typeof(f.value -> 'geometry') = 'object';
