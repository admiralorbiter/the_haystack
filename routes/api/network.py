from collections import defaultdict
from itertools import combinations

from flask import jsonify, request
from sqlalchemy import func

from models import Organization, Program, ProgramOccupation, db
from routes.cip_utils import CIP_FAMILY_NAMES, cip_family_label

from . import api_v1_bp


@api_v1_bp.route("/network/providers")
def network_providers_data():
    """
    Returns nodes and edges for the training ecosystem graph.
    Query params:
    - edge: cip, soc, both (default)
    - limit: node cap (default 50)
    """
    edge_mode = request.args.get("edge", "both").lower()
    if edge_mode not in ("cip", "soc", "both"):
        edge_mode = "both"

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    # 1. Fetch top providers by completions
    top_orgs = (
        db.session.query(
            Organization,
            func.sum(Program.completions).label("total_completions"),
        )
        .outerjoin(Program, Program.org_id == Organization.org_id)
        .filter(Organization.org_type == "training", Organization.is_active == True)
        .group_by(Organization.org_id)
        .order_by(func.sum(Program.completions).desc().nulls_last())
        .limit(limit)
        .all()
    )

    if not top_orgs:
        return jsonify({"nodes": [], "edges": [], "meta": {}})

    org_map = {row.Organization.org_id: row for row in top_orgs}
    org_ids = list(org_map.keys())

    # 2. Extract CIPs per provider (family level)
    cip_query = (
        db.session.query(Program.org_id, Program.cip)
        .filter(Program.org_id.in_(org_ids), Program.cip.isnot(None))
        .all()
    )

    org_cips = defaultdict(set)       # org_id → set of 2-digit family codes
    family_program_counts = defaultdict(lambda: defaultdict(int))

    for org_id, cip in cip_query:
        family = cip.split(".")[0][:2].zfill(2) if "." in cip else cip[:2].zfill(2)
        org_cips[org_id].add(family)
        family_program_counts[org_id][family] += 1

    # Dominant CIP family per org
    dominant_cip = {}
    for org_id in org_ids:
        counts = family_program_counts[org_id]
        if counts:
            dominant_cip[org_id] = max(counts, key=counts.get)
        else:
            dominant_cip[org_id] = "—"

    # SOCs per provider
    soc_query = (
        db.session.query(Program.org_id, ProgramOccupation.soc)
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .filter(Program.org_id.in_(org_ids))
        .all()
    )

    org_socs = defaultdict(set)
    for org_id, soc in soc_query:
        org_socs[org_id].add(soc)

    # 3. Compute pairwise edges, now including shared code lists
    cip_edges = {}   # pair_key → (weight, [shared_family_codes])
    soc_edges = {}   # pair_key → (weight, [shared_soc_codes])

    for org_a, org_b in combinations(org_ids, 2):
        pair_key = tuple(sorted([org_a, org_b]))

        if edge_mode in ("cip", "both"):
            shared = org_cips[org_a].intersection(org_cips[org_b])
            if len(shared) >= 2:
                cip_edges[pair_key] = (len(shared), sorted(shared))

        if edge_mode in ("soc", "both"):
            shared = org_socs[org_a].intersection(org_socs[org_b])
            if len(shared) >= 2:
                soc_edges[pair_key] = (len(shared), sorted(list(shared))[:5])  # cap list at 5 for payload size

    # 4. Compute global meta for gap analysis
    # Which CIP families appear in the current node set?
    family_provider_counts = defaultdict(int)
    for org_id in org_ids:
        for fam in org_cips[org_id]:
            family_provider_counts[fam] += 1

    # All CIP families in the universe
    all_families = {
        code: name for code, name in CIP_FAMILY_NAMES.items()
    }
    # Which families have 0, 1, or 2 providers (potentially underserved in top-N)
    gap_analysis = {
        fam: {
            "name": name,
            "count": family_provider_counts.get(fam, 0),
        }
        for fam, name in all_families.items()
        if family_provider_counts.get(fam, 0) <= 2
    }

    # 5. Build nodes
    nodes_out = []
    for org_id, row in org_map.items():
        org = row.Organization
        fam = dominant_cip[org_id]
        fam_label = cip_family_label(f"{fam}.0000") if fam != "—" else "Unknown"
        all_fams = sorted(org_cips[org_id])   # all CIP families this org operates in

        nodes_out.append(
            {
                "data": {
                    "id": org_id,
                    "label": org.name,
                    "type": org.org_type,
                    "completions": int(row.total_completions) if row.total_completions else 0,
                    "cip_family": fam,
                    "cip_label": fam_label,
                    "cip_families": all_fams,   # all families — used for filter chips
                    "city": org.city or "",
                    "state": org.state or "",
                    "url": f"/providers/{org_id}",
                }
            }
        )

    # 6. Build edges
    edges_out = []
    all_pairs = set(cip_edges.keys()).union(set(soc_edges.keys()))

    for org_a, org_b in all_pairs:
        c_data = cip_edges.get((org_a, org_b), (0, []))
        s_data = soc_edges.get((org_a, org_b), (0, []))
        c_weight, c_codes = c_data
        s_weight, s_codes = s_data

        if edge_mode == "both":
            if c_weight > 0 and s_weight > 0:
                e_type = "both"
                e_weight = c_weight + s_weight
                label = f"{c_weight} shared fields · {s_weight} shared occupations"
            elif c_weight > 0:
                e_type = "cip"
                e_weight = c_weight
                label = f"{c_weight} shared training fields"
            else:
                e_type = "soc"
                e_weight = s_weight
                label = f"{s_weight} shared occupations"
        elif edge_mode == "cip":
            e_type = "cip"
            e_weight = c_weight
            label = f"{c_weight} shared training fields"
        else:
            e_type = "soc"
            e_weight = s_weight
            label = f"{s_weight} shared occupations"

        # Resolve human-readable names for shared CIP families
        shared_cip_names = [
            {"code": code, "name": CIP_FAMILY_NAMES.get(code, code)}
            for code in c_codes
        ]

        edges_out.append(
            {
                "data": {
                    "id": f"e_{org_a}_{org_b}",
                    "source": org_a,
                    "target": org_b,
                    "weight": e_weight,
                    "edge_type": e_type,
                    "label": label,
                    "shared_cips": shared_cip_names,   # [{code, name}]
                    "shared_soc_count": s_weight,
                }
            }
        )

    meta = {
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "gap_analysis": gap_analysis,
        "family_counts": dict(family_provider_counts),
    }

    return jsonify({"nodes": nodes_out, "edges": edges_out, "meta": meta})
