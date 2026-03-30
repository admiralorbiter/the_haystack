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

SOC_MAJOR_GROUPS = {
    "11": "Management Occupations",
    "13": "Business and Financial Operations Occupations",
    "15": "Computer and Mathematical Occupations",
    "17": "Architecture and Engineering Occupations",
    "19": "Life, Physical, and Social Science Occupations",
    "21": "Community and Social Service Occupations",
    "23": "Legal Occupations",
    "25": "Educational Instruction and Library Occupations",
    "27": "Arts, Design, Entertainment, Sports, and Media Occupations",
    "29": "Healthcare Practitioners and Technical Occupations",
    "31": "Healthcare Support Occupations",
    "33": "Protective Service Occupations",
    "35": "Food Preparation and Serving Related Occupations",
    "37": "Building and Grounds Cleaning and Maintenance Occupations",
    "39": "Personal Care and Service Occupations",
    "41": "Sales and Related Occupations",
    "43": "Office and Administrative Support Occupations",
    "45": "Farming, Fishing, and Forestry Occupations",
    "47": "Construction and Extraction Occupations",
    "49": "Installation, Maintenance, and Repair Occupations",
    "51": "Production Occupations",
    "53": "Transportation and Material Moving Occupations",
    "55": "Military Specific Occupations",
}

SECTOR_NAMES = {
    '11': 'Agriculture, Forestry, Fishing and Hunting',
    '21': 'Mining, Quarrying, and Oil and Gas Extraction',
    '22': 'Utilities',
    '23': 'Construction',
    '31-33': 'Manufacturing',
    '42': 'Wholesale Trade',
    '44-45': 'Retail Trade',
    '48-49': 'Transportation and Warehousing',
    '51': 'Information',
    '52': 'Finance and Insurance',
    '53': 'Real Estate and Rental and Leasing',
    '54': 'Professional, Scientific, and Technical Services',
    '55': 'Management of Companies and Enterprises',
    '56': 'Administrative and Support and Waste Management',
    '61': 'Educational Services',
    '62': 'Health Care and Social Assistance',
    '71': 'Arts, Entertainment, and Recreation',
    '72': 'Accommodation and Food Services',
    '81': 'Other Services (except Public Administration)',
    '92': 'Public Administration'
}

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
    EMPLOYEES_TOTAL_RANGE = "employees_total_range"


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
    naics_code: Mapped[str] = mapped_column(String(6), nullable=True)
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
    description: Mapped[str] = mapped_column(String, nullable=True)
    soc_major: Mapped[str] = mapped_column(String(10), nullable=True)
    soc_minor: Mapped[str] = mapped_column(String(10), nullable=True)
    job_zone: Mapped[int] = mapped_column(Integer, nullable=True)
    bright_outlook: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    automation_risk: Mapped[float] = mapped_column(Float, nullable=True)
    remote_capable: Mapped[bool] = mapped_column(Boolean, nullable=True, server_default="0")
    
    wages = relationship("OccupationWage", back_populates="occupation", cascade="all, delete-orphan")
    tasks = relationship("OccupationTask", back_populates="occupation", cascade="all, delete-orphan")
    tech_skills = relationship("OccupationTechSkill", back_populates="occupation", cascade="all, delete-orphan")
    related = relationship("RelatedOccupation", back_populates="occupation", foreign_keys="RelatedOccupation.soc", cascade="all, delete-orphan")
    aliases = relationship("OccupationAlias", back_populates="occupation", cascade="all, delete-orphan")
    skills = relationship("OccupationSkill", back_populates="occupation", cascade="all, delete-orphan")
    education = relationship("OccupationEducation", back_populates="occupation", cascade="all, delete-orphan")
    projection = relationship("OccupationProjection", uselist=False, back_populates="occupation", cascade="all, delete-orphan")
    industries = relationship("OccupationIndustry", back_populates="occupation", cascade="all, delete-orphan")

    @property
    def soc_major_title(self) -> str:
        return SOC_MAJOR_GROUPS.get(self.soc_major, "Unknown Major Group") if self.soc_major else "Unknown Major Group"


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


class OccupationTask(db.Model):
    __tablename__ = "occupation_task"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    task_statement: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=True)
    
    occupation = relationship("Occupation", back_populates="tasks", foreign_keys=[soc])


class OccupationTechSkill(db.Model):
    __tablename__ = "occupation_tech_skill"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    example: Mapped[str] = mapped_column(String, nullable=False)
    hot_technology: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    
    occupation = relationship("Occupation", back_populates="tech_skills", foreign_keys=[soc])


class RelatedOccupation(db.Model):
    __tablename__ = "related_occupation"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    related_soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    relatedness_tier: Mapped[str] = mapped_column(String(50), nullable=True)
    index_score: Mapped[float] = mapped_column(Float, nullable=True)
    
    occupation = relationship("Occupation", back_populates="related", foreign_keys=[soc])
    related_occupation = relationship("Occupation", foreign_keys=[related_soc])


class OccupationAlias(db.Model):
    __tablename__ = "occupation_alias"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    alias_title: Mapped[str] = mapped_column(String, nullable=False)
    short_title: Mapped[str] = mapped_column(String, nullable=True)

    occupation = relationship("Occupation", back_populates="aliases", foreign_keys=[soc])


class OccupationSkill(db.Model):
    __tablename__ = "occupation_skill"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    element_name: Mapped[str] = mapped_column(String(255), nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    occupation = relationship("Occupation", back_populates="skills", foreign_keys=[soc])


class OccupationEducation(db.Model):
    __tablename__ = "occupation_education"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    ed_level_code: Mapped[int] = mapped_column(Integer, nullable=False)
    ed_level_label: Mapped[str] = mapped_column(String(100), nullable=True)
    pct_workers: Mapped[float] = mapped_column(Float, nullable=False)
    
    occupation = relationship("Occupation", back_populates="education", foreign_keys=[soc])


class OccupationProjection(db.Model):
    __tablename__ = "occupation_projection"
    
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), primary_key=True)
    emp_2024: Mapped[int] = mapped_column(Integer, nullable=True)
    emp_2034: Mapped[int] = mapped_column(Integer, nullable=True)
    pct_change: Mapped[float] = mapped_column(Float, nullable=True)
    annual_openings: Mapped[int] = mapped_column(Integer, nullable=True)
    
    occupation = relationship("Occupation", back_populates="projection", foreign_keys=[soc])


class OccupationIndustry(db.Model):
    __tablename__ = "occupation_industry"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    soc: Mapped[str] = mapped_column(ForeignKey("occupation.soc"), nullable=False, index=True)
    naics: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_title: Mapped[str] = mapped_column(String, nullable=False)
    employment_2024: Mapped[int] = mapped_column(Integer, nullable=True)
    pct_of_occupation: Mapped[float] = mapped_column(Float, nullable=True)
    
    occupation = relationship("Occupation", back_populates="industries", foreign_keys=[soc])


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


class IndustryQCEW(db.Model):
    __tablename__ = "industry_qcew"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    naics: Mapped[str] = mapped_column(String(20), nullable=False)
    county_fips: Mapped[str] = mapped_column(String(5), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    establishments: Mapped[int] = mapped_column(Integer, nullable=True)
    employment: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_weekly_wage: Mapped[float] = mapped_column(Float, nullable=True)

Index("ix_industry_qcew_lookup", IndustryQCEW.naics, IndustryQCEW.county_fips)
Index("ix_industry_qcew_time", IndustryQCEW.year, IndustryQCEW.quarter)

class IndustryFlowJ2J(db.Model):
    __tablename__ = "industry_flow_j2j"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False) # 'MO' or 'KS'
    origin_naics: Mapped[str] = mapped_column(String(6), nullable=False)
    destination_naics: Mapped[str] = mapped_column(String(6), nullable=False)
    transitions: Mapped[int] = mapped_column(Integer, nullable=False)

Index("ix_industry_flow_dest", IndustryFlowJ2J.destination_naics)
Index("ix_industry_flow_orig", IndustryFlowJ2J.origin_naics)
