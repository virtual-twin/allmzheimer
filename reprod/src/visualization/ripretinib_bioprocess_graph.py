# file: src/visualization/ripretinib_bioprocess_graph.py
# This script reproduces the Ripretinib → Biological Processes → Alzheimer’s Pathology sample graph from the manuscript
# Please note the notion in the script that it only shows a selection of the biological processes (manually curated as stated in the manuscript)
# In the script it says "This is an example graph from the graph database containing a (manual) selection (8 of 76) of processes (green), AD pathology (blue), and the drug Ripretinib (pink)."
# This code generates a graph that shows all biological processes related to Ripretinib, to provide the full functional graph that could not be shown for layout reasons in the manuscript

import os
import sys
import logging
from typing import Dict, Tuple, List

import matplotlib.pyplot as plt
import networkx as nx
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Reuse pipeline logging
try:
    from src.utils.logging_config import setup_logging
except Exception:
    def setup_logging(*args, **kwargs):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

# ---- Setup ----
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

URI = os.getenv("uri")
USER = os.getenv("username")
PASSWORD = os.getenv("password")

EXPORTS_DIR = os.getenv("PLOTS_DIR", "/app/exports/plots")
os.makedirs(EXPORTS_DIR, exist_ok=True)
OUT_PNG = os.path.join(EXPORTS_DIR, "ripretinib_bioprocess_graph.png")

# Allow overrides via env; defaults provided
DRUG_NAME = os.getenv("RIPRETINIB_NAME", "Ripretinib")
DRUGBANK_ID = os.getenv("RIPRETINIB_DRUGBANK_ID", "DB14840")

# Colors
CLR_DRUG = "#7B3FE4"      # purple
CLR_BP   = "#009E73"      # green
CLR_ALZ  = "#0072B2"      # blue

def _short_id(n) -> str:
    try:
        eid = getattr(n, "element_id", None)
        if eid:
            return eid.split(":")[-1][-6:]
    except Exception:
        pass
    try:
        return str(n.id)[-6:]
    except Exception:
        return "node"

def _safe_label(n, role: str) -> str:
    """
    Produce a non-empty string label for plotting even if properties are missing.
    Preference order varies by role.
    """
    if n is None:
        return f"{role.upper()}?"

    # Pull dict-like props
    def _get(n, k):
        try:
            return n.get(k)
        except Exception:
            return None

    if role == "drug":
        for k in ("name", "drugbankId", "label"):
            v = _get(n, k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return f"Drug:{_short_id(n)}"

    if role == "bp":
        for k in ("goName", "label", "name"):
            v = _get(n, k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return f"BP:{_short_id(n)}"

    if role == "alz":
        # Your schema uses pathologyName
        v = _get(n, "pathologyName")
        if isinstance(v, str) and v.strip():
            return v.strip()
        return "Alzheimer"

    # default
    v = _get(n, "name") or _get(n, "label")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return f"{role}:{_short_id(n)}"

def fetch_subgraph(uri: str, user: str, password: str) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """
    Return nodes and edges for:
      Drug (Ripretinib)  -> (BiologicalProcess) -> (:Pathology {pathologyName:'Alzheimer'})
    Match drug by name OR DrugBank ID.
    Uses explicit relationships: AFFECTS and RELATED_TO.
    """
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            query = """
            MATCH (d:Drug)
            WHERE toLower(d.name) = toLower($drug_name) OR d.drugbankId = $drugbank_id
            OPTIONAL MATCH (d)-[:AFFECTS]->(bp:BiologicalProcess)
            OPTIONAL MATCH (bp)-[:RELATED_TO]->(alz:Pathology {pathologyName: 'Alzheimer'})
            RETURN d, collect(DISTINCT bp) AS bps, collect(DISTINCT alz) AS alzs
            """
            rec = session.run(query, drug_name=DRUG_NAME, drugbank_id=DRUGBANK_ID).single()
            if not rec:
                logger.warning("No records returned for drug name '%s' or DrugBank ID '%s'.", DRUG_NAME, DRUGBANK_ID)
                return [], []

            d = rec["d"]
            bps = [n for n in rec["bps"] if n is not None]
            alzs = [n for n in rec["alzs"] if n is not None]

            if not bps:
                logger.warning("No BiologicalProcess nodes found linked via :AFFECTS. Plot will contain the drug only.")

            if not alzs:
                logger.info("No (:Pathology {pathologyName:'Alzheimer'}) node found via :RELATED_TO; plotting Drug→BP only.")

            nodes = []
            edges = []

            # Labels (safe)
            drug_label = _safe_label(d, "drug")
            nodes.append({"label": drug_label, "role": "drug"})

            bp_labels = []
            for bp in bps:
                bl = _safe_label(bp, "bp")
                bp_labels.append(bl)
                nodes.append({"label": bl, "role": "bp"})
                edges.append((drug_label, bl))

            alz_labels = []
            for alz in alzs:
                al = _safe_label(alz, "alz")
                alz_labels.append(al)
                nodes.append({"label": al, "role": "alz"})

            for bl in bp_labels:
                for al in alz_labels:
                    edges.append((bl, al))

            # Dedup nodes by label
            nodes = list({n["label"]: n for n in nodes}.values())
            # Dedup edges
            edges = list(dict.fromkeys(edges))
            return nodes, edges
    finally:
        driver.close()

def build_and_plot(nodes: List[Dict], edges: List[Tuple[str, str]], out_png: str) -> None:
    if not nodes:
        logger.error("No nodes to plot. Aborting figure creation.")
        return

    G = nx.DiGraph()
    for n in nodes:
        # Guard against None labels
        label = n.get("label") or "node"
        G.add_node(label, role=n.get("role", "other"))
    for s, t in edges:
        if s in G and t in G:
            G.add_edge(s, t)

    # Reproducible layout
    pos = nx.spring_layout(G, seed=42, k=0.65)

    # Color by role
    colors = []
    for n in G.nodes():
        role = G.nodes[n].get("role")
        if role == "drug":
            colors.append(CLR_DRUG)
        elif role == "bp":
            colors.append(CLR_BP)
        elif role == "alz":
            colors.append(CLR_ALZ)
        else:
            colors.append("#888888")

    plt.figure(figsize=(14, 10))
    ax = plt.gca()
    ax.set_facecolor("#F8F9F9")
    plt.gcf().set_facecolor("#F8F9F9")

    nx.draw_networkx_edges(G, pos, edge_color="#BBBBBB", arrows=True, arrowstyle="-|>", arrowsize=15, width=1.5, alpha=0.8)
    nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=850, linewidths=1.5, edgecolors="k")
    nx.draw_networkx_labels(G, pos, font_size=10, font_color="#1C2833", font_weight="bold")

    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=CLR_DRUG, edgecolor='k', label='Ripretinib (Drug)'),
        Patch(facecolor=CLR_BP, edgecolor='k', label='Biological Process'),
        Patch(facecolor=CLR_ALZ, edgecolor='k', label="Alzheimer's Pathology"),
    ]
    plt.legend(handles=legend_handles, loc="best", frameon=True, facecolor="white", edgecolor="none", framealpha=0.9)

    plt.title("Ripretinib → Biological Processes → Alzheimer’s Pathology", fontsize=14, pad=12, color="#2C3E50")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png, dpi=600, bbox_inches="tight", facecolor="#F8F9F9", edgecolor="none")
    logger.info("Graph exported to %s", out_png)
    plt.close()

def main() -> int:
    if not (URI and USER is not None and PASSWORD is not None):
        logger.critical("Neo4j credentials missing. Check .env (uri, username, password).")
        return 2

    nodes, edges = fetch_subgraph(URI, USER, PASSWORD)
    if not nodes:
        logger.critical("No subgraph found for '%s'/'%s'. Nothing to plot.", DRUG_NAME, DRUGBANK_ID)
        return 1

    build_and_plot(nodes, edges, OUT_PNG)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())