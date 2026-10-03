"""Persistent entities. ``database/schema.sql`` mirrors these for PostgreSQL+PostGIS.

Conventions
-----------
* ``is_demo`` marks synthetic seed-pack rows. They are always badged DEMO in
  the UI and removable per seed pack from the Control Board.
* Runs are append-only provenance records; nothing overwrites them.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every engine (SQLite drops tzinfo)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Destination(Base):
    __tablename__ = 'destinations'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(160), default='')
    country: Mapped[str] = mapped_column(String(80), default='Bangladesh')
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default='')
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)   # template key, e.g. visitor_flow
    name: Mapped[str] = mapped_column(String(192))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='draft')  # draft|validated|archived
    frequency: Mapped[str] = mapped_column(String(16), default='monthly')
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    variable_defs: Mapped[list] = mapped_column(JSON, default=list)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint('destination_id', 'kind', 'name', 'version'),)


class Observation(Base):
    __tablename__ = 'observations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id', ondelete='CASCADE'), index=True)
    destination_id: Mapped[str] = mapped_column(String(48), index=True)
    period: Mapped[str] = mapped_column(String(16), index=True)      # YYYY | YYYY-MM | YYYY-MM-DD | YYYY-Qn
    variable: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default='')
    quality_flag: Mapped[str] = mapped_column(String(16), default='ok')  # ok|estimated|missing|outlier
    import_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    __table_args__ = (UniqueConstraint('dataset_id', 'period', 'variable'),)


class ImportRecord(Base):
    """One committed import. ``file_hash`` makes imports idempotent."""
    __tablename__ = 'imports'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id', ondelete='CASCADE'), index=True)
    file_name: Mapped[str] = mapped_column(String(255), default='')
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_format: Mapped[str] = mapped_column(String(16), default='csv')
    layout: Mapped[str] = mapped_column(String(8), default='long')
    encoding: Mapped[str] = mapped_column(String(24), default='utf-8')
    delimiter: Mapped[str] = mapped_column(String(4), default=',')
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('dataset_id', 'file_hash'),)


class Run(Base):
    """Unified, append-only provenance record for calculations, forecasts and models."""
    __tablename__ = 'runs'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)        # calculation|forecast|model
    method_id: Mapped[str] = mapped_column(String(96), index=True)
    method_version: Mapped[str] = mapped_column(String(32))
    destination_id: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    dataset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
    method_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    software_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default='success')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str] = mapped_column(String(192), default='')
    rerun_of: Mapped[str | None] = mapped_column(String(48), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class MethodState(Base):
    """Enable/disable switch for registered calculations (Control Board)."""
    __tablename__ = 'method_state'
    method_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ModelPackage(Base):
    __tablename__ = 'models'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(192))
    task: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default='')
    framework: Mapped[str] = mapped_column(String(64))
    source_repo: Mapped[str] = mapped_column(String(512), default='')
    source_ref: Mapped[str] = mapped_column(String(128), default='')
    license: Mapped[str] = mapped_column(String(64), default='')
    training_data: Mapped[str] = mapped_column(Text, default='')
    input_variables: Mapped[list] = mapped_column(JSON, default=list)
    output_variables: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default='enabled')
    package_path: Mapped[str] = mapped_column(String(1024))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    installed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Scenario(Base):
    __tablename__ = 'scenarios'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(192))
    notes: Mapped[str] = mapped_column(Text, default='')
    run_id: Mapped[str] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Asset(Base):
    """Cultural & natural heritage asset registry."""
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    name: Mapped[str] = mapped_column(String(192))
    asset_type: Mapped[str] = mapped_column(String(16), default='natural')   # natural|cultural|mixed
    category: Mapped[str] = mapped_column(String(64), default='')
    condition: Mapped[str] = mapped_column(String(16), default='fair')        # good|fair|poor|critical
    threats: Mapped[list] = mapped_column(JSON, default=list)
    protection_status: Mapped[str] = mapped_column(String(96), default='unprotected')
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gis_layer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_assessed: Mapped[str] = mapped_column(String(10), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Incident(Base):
    __tablename__ = 'incidents'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    occurred_at: Mapped[str] = mapped_column(String(20))
    hazard: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16), default='minor')   # minor|moderate|major|critical
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(16), default='open')      # open|monitoring|closed
    response: Mapped[str] = mapped_column(Text, default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class EarlyWarning(Base):
    __tablename__ = 'warnings'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    hazard: Mapped[str] = mapped_column(String(48))
    level: Mapped[str] = mapped_column(String(16), default='watch')      # advisory|watch|warning|emergency
    issued_at: Mapped[str] = mapped_column(String(20))
    valid_until: Mapped[str] = mapped_column(String(20), default='')
    message: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[str] = mapped_column(String(192), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ReadinessItem(Base):
    __tablename__ = 'readiness_items'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    category: Mapped[str] = mapped_column(String(48))
    item: Mapped[str] = mapped_column(String(255))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str] = mapped_column(String(96), default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class InfraProject(Base):
    __tablename__ = 'infra_projects'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey('destinations.id'), index=True)
    name: Mapped[str] = mapped_column(String(192))
    category: Mapped[str] = mapped_column(String(48), default='access')
    stage: Mapped[str] = mapped_column(String(16), default='planned')    # proposed|planned|building|done|stalled
    budget_bdt_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    start: Mapped[str] = mapped_column(String(10), default='')
    end: Mapped[str] = mapped_column(String(10), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class GisLayer(Base):
    __tablename__ = 'gis_layers'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(48), default='custom')
    destination_id: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    geojson: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(512), default='')
    color: Mapped[str] = mapped_column(String(16), default='')
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Brief(Base):
    __tablename__ = 'briefs'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    destination_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    run_ids: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default='')
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    markdown: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Publication(Base):
    __tablename__ = 'publications'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    authors: Mapped[str] = mapped_column(String(512), default='')
    pub_type: Mapped[str] = mapped_column(String(32), default='policy-brief')
    status: Mapped[str] = mapped_column(String(16), default='draft')  # idea|draft|review|submitted|published
    venue: Mapped[str] = mapped_column(String(255), default='')
    due: Mapped[str] = mapped_column(String(10), default='')
    brief_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(192), default='')
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(64), default='local-user')


class AppSetting(Base):
    __tablename__ = 'app_settings'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)


# Ordered for backup/restore (parents before children).
ALL_TABLES = [Destination, Dataset, ImportRecord, Observation, Run, MethodState, ModelPackage,
              Scenario, Asset, Incident, EarlyWarning, ReadinessItem, InfraProject, GisLayer, Brief,
              Publication, AuditLog, AppSetting]
