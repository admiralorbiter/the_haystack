# Haystack SQLAlchemy models
# See HAYSTACK_EPICS.md Epic 1 for the full schema spec.
# Tables to define: geo_area, organization, org_alias, program, occupation,
#                   program_occupation, civic_signal, relationship,
#                   dataset_source, region, region_county

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
