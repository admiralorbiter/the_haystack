# The Haystack — Dataset Onboarding Template

Use this template before adding any new dataset.

---

## 1. Dataset identity
- **Dataset name:**
- **Owner / source organization:**
- **Source URL:**
- **License / use restrictions:**
- **Refresh cadence:**
- **Geographic coverage:**
- **Time coverage:**
- **Primary contact / docs:**

---

## 2. Product purpose
### What user question does this answer?
- 
- 
- 

### Why is this worth adding now?
- 

### Which Haystack entity does it primarily enrich?
- [ ] Geography
- [ ] Organization
- [ ] Program / Offering
- [ ] Work / Opportunity
- [ ] Civic Signal

---

## 3. Data shape
- **Grain:** one row per what?
- **Primary identifiers:**
- **Possible join keys:**
- **Spatial keys:**
- **Time keys:**
- **Freshness field:**
- **Known null / suppression patterns:**

### Required mappings
- joins to `organization`?
- joins to `program`?
- joins to `occupation` / `industry`?
- joins to `geo_area`?

---

## 4. Minimum viable fields
### Must-have fields for V1
- 
- 
- 

### Nice-to-have fields for later
- 
- 
- 

---

## 5. Loader spec
- source file/API format:
- cache location:
- loader script name:
- reset behavior:
- idempotent upsert strategy:
- QA checks:
- row-count logging:
- bad-row behavior:

### Required QA checks
- [ ] expected columns present
- [ ] key formats validated
- [ ] duplicate keys handled
- [ ] null-rate reviewed
- [ ] freshness captured
- [ ] source metadata recorded

---

## 6. UI contract
### Directory surface
- list title:
- default columns/cards:
- default sort:
- quick filters:
- advanced filters:

### Detail surface
- page title pattern:
- snapshot metrics (max 6):
- tabs used:
- primary chart/table:
- map support? yes/no
- compare support? yes/no

### Methods copy
- what does the dataset measure?
- what does it not measure?
- common misinterpretations:
- suppression/caveats:

---

## 7. Performance budget
- max payload size target:
- server query target:
- pagination plan:
- clustering / tiling needed?:
- precomputed aggregates needed?:

### Rules
- no giant full-table payloads by default
- no map layer without clustering if point-heavy
- no detail page with N+1 queries

---

## 8. UX risks
### What could confuse users?
- 
- 

### What terminology needs translation?
- raw source term:
- UI label:

### What should stay out of V1?
- 
- 

---

## 9. Ship checklist
- [ ] loader implemented
- [ ] dataset source metadata recorded
- [ ] searchable entity exposed
- [ ] directory page uses shared template
- [ ] detail page uses shared template
- [ ] data freshness shown
- [ ] methods text written
- [ ] empty states written
- [ ] compare or map support added if relevant
- [ ] tests added
- [ ] docs updated

---

## 10. Post-ship review
### What worked?
- 

### What broke the shell?
- 

### What reusable component or pattern emerged?
- 

### Should this dataset stay core, be optional, or remain experimental?
- [ ] Core
- [ ] Optional
- [ ] Experimental
