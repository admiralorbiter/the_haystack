"""
SQLAlchemy Models for The Haystack

Follows Epic 1 PRD schema:
- Python-side UUID4 generation for org_id and program_id
- Declarative Base class config
"""

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)


class PageView(db.Model):
    __tablename__ = "page_view"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    query_params: Mapped[str] = mapped_column(String(1000), nullable=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SearchEvent(db.Model):
    __tablename__ = "search_event"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class DatasetSource(db.Model):
    __tablename__ = "dataset_source"
    
    source_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    record_count: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)


class Region(db.Model):
    __tablename__ = "region"
    
    region_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_lat: Mapped[float] = mapped_column(Float, nullable=True)
    default_lon: Mapped[float] = mapped_column(Float, nullable=True)
    default_zoom: Mapped[int] = mapped_column(Integer, default=10)


class RegionCounty(db.Model):
    __tablename__ = "region_county"
    
    region_id: Mapped[str] = mapped_column(ForeignKey("region.region_id"), primary_key=True)
    county_fips: Mapped[str] = mapped_column(String(5), primary_key=True)
    county_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)


class GeoArea(db.Model):
    __tablename__ = "geo_area"
    
    geoid: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # zip, tract, county, metro
    state: Mapped[str] = mapped_column(String(2), nullable=True)
    county_fips: Mapped[str] = mapped_column(String(5), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)


class OrgFactType:
    """Standardized keys for the org_fact EAV table."""
    REVENUE = "revenue"
    EXPENSES = "expenses"
    NET_INCOME = "net_income"
    EMPLOYEES_TOTAL = "employees_total"
    H1B_PETITIONS = "h1b_petitions"
    WAGE_AVG = "wage_avg"


class Organization(db.Model):
    __tablename__ = "organization"
    
    org_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'training', 'employer', etc.
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(2), nullable=True)
    county_fips: Mapped[str] = mapped_column(String(5), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    website: Mapped[str] = mapped_column(String(500), nullable=True)
    unitid: Mapped[str] = mapped_column(String(50), nullable=True)
    ein: Mapped[str] = mapped_column(String(50), nullable=True)
    is_apprenticeship_partner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    apprenticeship_role: Mapped[str] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    last_seen_in_source: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    programs = relationship("Program", back_populates="organization")
    contacts = relationship("OrgContact", back_populates="organization", cascade="all, delete-orphan")
    facts = relationship("OrgFact", back_populates="organization", cascade="all, delete-orphan")
    demographics = relationship("OrganizationDemographics", uselist=False, back_populates="organization", cascade="all, delete-orphan")
    completions_demo = relationship("OrganizationCompletionsDemographics", uselist=False, back_populates="organization", cascade="all, delete-orphan")

Index("ix_organization_county_fips", Organization.county_fips)


class OrgFact(db.Model):
    __tablename__ = "org_fact"
    
    fact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value_num: Mapped[float] = mapped_column(Float, nullable=True)
    value_text: Mapped[str] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="facts")


class OrgAlias(db.Model):
    __tablename__ = "org_alias"
    
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=True)


class OrgContact(db.Model):
    __tablename__ = "org_contact"
    
    contact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    contact_role: Mapped[str] = mapped_column(String(100), nullable=True) # e.g. "Apprenticeship Sponsor"

    organization = relationship("Organization", back_populates="contacts")


class Program(db.Model):
    __tablename__ = "program"
    
    program_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    cip: Mapped[str] = mapped_column(String(10), nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=True)
    completions: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=True)
    is_wioa_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    is_apprenticeship: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    organization = relationship("Organization", back_populates="programs")
    demographics = relationship("ProgramDemographics", uselist=False, back_populates="program", cascade="all, delete-orphan")

Index("ix_program_org_id", Program.org_id)
Index("ix_program_cip", Program.cip)


class Occupation(db.Model):
    __tablename__ = "occupation"
    
    soc: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    soc_major: Mapped[str] = mapped_column(String(10), nullable=True)
    soc_minor: Mapped[str] = mapped_column(String(10), nullable=True)
    job_zone: Mapped[int] = mapped_column(Integer, nullable=True)
    bright_outlook: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    
    wages = relationship("OccupationWage", back_populates="occupation", cascade="all, delete-orphan")


class OccupationWage(db.Model):
    __tablename__ = "occupation_wage"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False)
    area_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'national', 'state', 'msa'
    area_code: Mapped[str] = mapped_column(String(20), nullable=False)
    area_name: Mapped[str] = mapped_column(String(255), nullable=True)
    
    employment_count: Mapped[int] = mapped_column(Integer, nullable=True)
    annual_mean_wage: Mapped[float] = mapped_column(Float, nullable=True)
    median_wage: Mapped[float] = mapped_column(Float, nullable=True)
    pct_25_wage: Mapped[float] = mapped_column(Float, nullable=True)
    pct_75_wage: Mapped[float] = mapped_column(Float, nullable=True)
    
    occupation = relationship("Occupation", back_populates="wages")

Index("ix_occupation_wage_soc", OccupationWage.soc)
Index("ix_occupation_wage_area", OccupationWage.area_type, OccupationWage.area_code)


class ProgramOccupation(db.Model):
    __tablename__ = "program_occupation"
    
    program_id: Mapped[str] = mapped_column(ForeignKey("program.program_id"), primary_key=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)

Index("ix_program_occupation_program_id", ProgramOccupation.program_id)


class CivicSignal(db.Model):
    __tablename__ = "civic_signal"
    
    signal_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    geoid: Mapped[str] = mapped_column(String(20), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)


class Relationship(db.Model):
    __tablename__ = "relationship"
    
    rel_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    to_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    to_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rel_type: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class OrganizationDemographics(db.Model):
    __tablename__ = "organization_demographics"
    
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), primary_key=True)
    total_enrollment: Mapped[int] = mapped_column(Integer, nullable=True)
    pct_men: Mapped[float] = mapped_column(Float, nullable=True)
    pct_women: Mapped[float] = mapped_column(Float, nullable=True)
    pct_white: Mapped[float] = mapped_column(Float, nullable=True)
    pct_black: Mapped[float] = mapped_column(Float, nullable=True)
    pct_hispanic: Mapped[float] = mapped_column(Float, nullable=True)
    pct_asian: Mapped[float] = mapped_column(Float, nullable=True)
    pct_native: Mapped[float] = mapped_column(Float, nullable=True)
    pct_pacific: Mapped[float] = mapped_column(Float, nullable=True)
    pct_two_or_more: Mapped[float] = mapped_column(Float, nullable=True)
    pct_unknown: Mapped[float] = mapped_column(Float, nullable=True)
    pct_non_resident: Mapped[float] = mapped_column(Float, nullable=True)

    organization = relationship("Organization", back_populates="demographics")


class OrganizationCompletionsDemographics(db.Model):
    __tablename__ = "organization_completions_demo"
    
    org_id: Mapped[str] = mapped_column(ForeignKey("organization.org_id"), primary_key=True)
    total_completions: Mapped[int] = mapped_column(Integer, nullable=True)
    pct_men: Mapped[float] = mapped_column(Float, nullable=True)
    pct_women: Mapped[float] = mapped_column(Float, nullable=True)
    pct_white: Mapped[float] = mapped_column(Float, nullable=True)
    pct_black: Mapped[float] = mapped_column(Float, nullable=True)
    pct_hispanic: Mapped[float] = mapped_column(Float, nullable=True)
    pct_asian: Mapped[float] = mapped_column(Float, nullable=True)
    pct_native: Mapped[float] = mapped_column(Float, nullable=True)
    pct_pacific: Mapped[float] = mapped_column(Float, nullable=True)
    pct_two_or_more: Mapped[float] = mapped_column(Float, nullable=True)
    pct_unknown: Mapped[float] = mapped_column(Float, nullable=True)
    pct_non_resident: Mapped[float] = mapped_column(Float, nullable=True)

    organization = relationship("Organization", back_populates="completions_demo")


class ProgramDemographics(db.Model):
    __tablename__ = "program_demographics"
    
    program_id: Mapped[str] = mapped_column(ForeignKey("program.program_id"), primary_key=True)
    total_completions: Mapped[int] = mapped_column(Integer, nullable=True)
    pct_men: Mapped[float] = mapped_column(Float, nullable=True)
    pct_women: Mapped[float] = mapped_column(Float, nullable=True)
    pct_white: Mapped[float] = mapped_column(Float, nullable=True)
    pct_black: Mapped[float] = mapped_column(Float, nullable=True)
    pct_hispanic: Mapped[float] = mapped_column(Float, nullable=True)
    pct_asian: Mapped[float] = mapped_column(Float, nullable=True)
    pct_native: Mapped[float] = mapped_column(Float, nullable=True)
    pct_pacific: Mapped[float] = mapped_column(Float, nullable=True)
    pct_two_or_more: Mapped[float] = mapped_column(Float, nullable=True)
    pct_unknown: Mapped[float] = mapped_column(Float, nullable=True)
    pct_non_resident: Mapped[float] = mapped_column(Float, nullable=True)

    program = relationship("Program", back_populates="demographics")
