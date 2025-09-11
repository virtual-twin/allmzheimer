#!/usr/bin/env bash
# file: entrypoint.sh
# Please make sure to create a .env file in the reprod directory and to place the datasets in the reprod/datasets directory
# You may refer to the example.env file for the required variables
# You may refer to the reprod/datasets/README_datasets.md file for the required datasets
# Please note - if you do not place the datasets in the reprod/datasets directory, you will need to change the paths in the .env file
# and perhaps you need to mount the datasets directory into the container in the docker-compose.yml file
# We therefore strongly recommend placing the datasets in the reprod/datasets directory to simplify results reproduction


set -euo pipefail

# Load /app/.env when present
if [[ -f "/app/.env" ]]; then
  set -a
  source /app/.env
  set +a
else
  echo "Warning: /app/.env not found. Using defaults."
fi


echo "== Step 1: Filter ARUK-UCL TSV =="
: "${input_path_arukucl:=/app/datasets/ARUK-UCL-GO-terms.tsv}"
: "${output_path_arukucl:=/app/datasets/filtered_ARUK-UCL-GO-terms.tsv}"

echo "Input:  ${input_path_arukucl}"
echo "Output: ${output_path_arukucl}"


python -m src.pipelines.filter_arukucl_for_bio_process
test -f "$output_path_arukucl" || { echo "Expected output missing: $output_path_arukucl"; exit 10; }


export BIOPROCESS_ARUK_UCL_GO_TERMS_TSV="${BIOPROCESS_ARUK_UCL_GO_TERMS_TSV:-$output_path_arukucl}"


: "${uri:=bolt://neo4j:7687}"
: "${username:=neo4j}"
if [[ -z "${password:-}" && -n "${NEO4J_AUTH:-}" ]]; then
  # NEO4J_AUTH is "neo4j/<password>"
  password="${NEO4J_AUTH#neo4j/}"
  export password
fi


: "${uri:?Neo4j 'uri' must be set (e.g., bolt://neo4j:7687)}"
: "${username:?Neo4j 'username' must be set}"
: "${password:?Neo4j 'password' must be set}"

echo "== Step 2: Import Biological Processes into Neo4j =="
python -m src.pipelines.add_arukucl_bioprocesses_to_neo4j

echo "== Step 3: Import DrugBank into Neo4j =="

# Ensure the XML path is present
# Please refer to the README_datasets.md file for details onthe required dataset
: "${DRUGBANK_XML:=/app/datasets/drugbank_full_dataset.xml}"
if [[ ! -f "$DRUGBANK_XML" ]]; then
  echo "DrugBank XML not found at DRUGBANK_XML=$DRUGBANK_XML"
  echo "Please mount it into ./datasets and/or set DRUGBANK_XML in .env"
  exit 20
fi

python -m src.pipelines.add_drugbank2neo4j

echo "== Step 4: Verify DrugBank unique count =="
python -m src.tests.verify_number_of_drugs || {
  echo "Drug count verification reported an error. Inspect logs above."; exit 30;
}

echo "== Step 5: Add Alzheimer's Pathology node and connect =="
python -m src.pipelines.add_alzheimer_pathology

echo "== Step 6: Map Drug.affectedGoProcess -> GO IDs via QuickGO =="
python -m src.pipelines.map_go_terms_for_drugs

echo "== Step 7: Connect Drug -> BiologicalProcess via GO IDs =="
python -m src.pipelines.connect_bioprocess_with_drug

echo "== Step 8: Verify AD-related drug count and BiologicalProcess count =="
python -m src.tests.verify_ad_drug_and_bioprocess_counts || {
  echo "Verification reported an error. Inspect logs above."; exit 40;
}

echo "== Step 9: Export CSVs (AD-related drugs, non-AD drugs, AD-related processes) =="
python -m src.pipelines.export_drug_and_process_csvs || {
  echo "CSV export failed. Inspect logs above."; exit 60;
}

echo "== Step 10: Remove island Drug nodes (no AFFECTS) and verify deletion count =="
python -m src.pipelines.remove_island_drugs || {
  echo "Island-drug deletion verification reported an error. Inspect logs above."; exit 50;
}

echo "== Step 11: Generate JSON prompts for LLM rating =="
python -m src.pipelines.rating_JSON_generator || {
  echo "JSON prompt generation failed. Inspect logs above."; exit 70;
}

echo "== Step 12: (Optional) Run LLM over ORIGINAL prompts =="
PROMPTS_DIRS="/app/exports/prompts" \
python -m src.pipelines.JSON_prompts2LLM || {
  echo "LLM prompt execution (original prompts) reported an error. Inspect logs above."; exit 80;
}

echo "== Step 13: Integrate LLM rating JSONs into the Neo4j graph =="
python -m src.pipelines.integrate_rating_jsons || {
  echo "Rating integration reported an error. Inspect logs above."; exit 90;
}

echo "== The database has been populated with the LLM ratings and is now ready for visualization =="
echo "== The script will now start to reproduce the plots presented in the paper =="
echo "== However, you may run your own experiments now by accessing the database =="

echo "== Step 14: Plot rating distributions across iterations =="
python -m src.visualization.plot_rating_densities || {
  echo "Plot generation failed. Inspect logs above."; exit 100;
}


echo "== Step 15: Rating distribution positioned by mean =="
python -m src.visualization.plot_rating_distribution_positioned_by_mean || {
  echo "Supplementary rating distribution plot failed. Inspect logs above."; exit 110;
}

echo "== Step 16: Top-20 rating distributions (main paper) =="
python -m src.visualization.plot_top20_rating_distributions || {
  echo "Top-20 rating distributions plot failed. Inspect logs above."; exit 120;
}

echo "== Step 17: Friedman test across rating iterations =="
python -m src.statistics.friedman_test_on_ratings || {
  echo "Friedman test failed. Inspect logs above."; exit 130;
}

echo "== Step 18: Export top-rated nodes to CSV =="
python -m src.statistics.export_top_rated_nodes || {
  echo "Top-rated export failed. Inspect logs above."; exit 140;
}

echo "== Step 19: Generate zero-shot prompts (name + ID only) =="
python -m src.pipelines.generate_zero_shot_prompts || {
  echo "Zero-shot prompt generation failed. Inspect logs above."; exit 80;
}

echo "== Step 20: (Optional) Run LLM over ZERO-SHOT prompts =="
PROMPTS_DIRS="/app/exports/prompts/zero_shot_prompts" \
python -m src.pipelines.JSON_prompts2LLM || {
  echo "LLM prompt execution (zero-shot prompts) reported an error. Inspect logs above."; exit 86;
}

echo "== Step 21: Integrate ZERO-SHOT LLM rating JSONs into the Neo4j graph =="
python -m src.pipelines.integrate_zero_shot_ratings || {
  echo "Zero-shot rating integration reported an error. Inspect logs above."; exit 91;
}


# ---- helper: on failure retry with conservative BLAS/Numba to enhance multiarch compatibility for
# UMAP steps----
run_umap_step () {
  local module="$1"
  local fail_code="$2"
  local fail_msg="$3"

  if ! python -m "$module"; then
    echo "First attempt failed for $module; retrying with conservative BLAS/Numba settings…"
    NUMBA_DISABLE_JIT=1 OPENBLAS_CORETYPE=NEHALEM OMP_NUM_THREADS=1 \
    python -m "$module" || {
      echo "$fail_msg"
      exit "$fail_code"
    }
  fi
}


echo "== Step 22: UMAP validation plot (literature list) =="
run_umap_step "src.visualization.umap_validation_plot" 120 \
"Validation UMAP plot failed. Inspect logs above. Please note that UMAP steps have specific requirements for the CPU/BLAS/JIT stack. Your PC might be lacking the vector instruction sets for this."

echo "== Step 23: Generate top-100 and top-30 drug lists for UMAP plots =="
python -m src.pipelines.generate_top_100_and_30_for_umap || {
  echo "Top list generation failed. Inspect logs above."
  exit 90
}

echo "== Step 24: UMAP plot of approaches using Ollama embeddings =="
run_umap_step "src.visualization.umap_approaches_plot" 110 \
"UMAP approaches plot failed. Inspect logs above. Please note that UMAP steps have specific requirements for the CPU/BLAS/JIT stack. Your PC might be lacking the vector instruction sets for this."

echo "== Step 25: UMAP (Top-30) annotated comparison plot =="
run_umap_step "src.visualization.umap_top30_annotated" 110 \
"UMAP Top-30 plot failed. Inspect logs above. Please note that UMAP steps have specific requirements for the CPU/BLAS/JIT stack. Your PC might be lacking the vector instruction sets for this."

echo "== Step 26: Compare approaches vs literature (top-50 via Ollama embeddings) =="
run_umap_step "src.statistics.calculate_closest_approach" 130 \
"Approach-vs-literature comparison failed. Inspect logs above. Please note that UMAP steps have specific requirements for the CPU/BLAS/JIT stack. Your PC might be lacking the vector instruction sets for this."


echo "== Step 27: Generate GO classification prompts =="
GO_CLASSIFICATION_DIR="/app/exports/GO_classification_prompts"

python -m src.pipelines.JSON_prompt_generator_GO_classification \
  --output-dir "$GO_CLASSIFICATION_DIR" || {
    echo "GO classification prompt generation failed. Inspect logs above."; exit 140;
}

# this step must be turned on by setting RUN_LLM=true in the .env file
echo "== Step 28: GO drug classification (LLM) =="
python -m src.pipelines.GO_drug_classification2LLM || {
  echo "GO drug classification LLM step failed. Inspect logs above."; exit 150;
}

echo "== Step 29: Integrate GO classifications into Neo4j =="
python -m src.pipelines.integrate_highly_rated_GO_classification_for_bio_process || {
  echo "GO classification integration failed. Inspect logs above."; exit 160;
}

echo "== Step 30: GO process plot =="
python -m src.visualization.GO_process_plot || {
  echo "GO process plot failed. Inspect logs above."; exit 170;
}

echo "== Step 31: Plot Ripretinib → Biological Processes → Alzheimer’s Pathology =="
python -m src.visualization.ripretinib_bioprocess_graph || {
  echo "Ripretinib subgraph plot failed. Inspect logs above."; exit 150;
}

# Please note that the clinical trials steps take a long time to run
# you may want to comment them out unless you are prepared for the script to run for several hours (depending on your machine, internet speed etc.)
# In our experience, the main bottleneck here is the response time of the clinical_trialsgov api
# (so even if you run this script on a fairly modern machine it might still take a while to complete)

echo "== Step 32: Fetch clinicaltrials.gov data for all Drug names =="
python -m src.pipelines.get_trialsgov_data || {
  echo "ClinicalTrials.gov fetch failed. Inspect logs above."; exit 150;
}


echo "== Step 33: ClinicalTrials.gov scatter plots =="
python -m src.visualization.trial_scatterplot || {
  echo "Trial scatterplot generation failed. Inspect logs above."; exit 120;
}

echo "== Step 34: Create clinical trials map plot =="
python -m src.visualization.map_plot || {
  echo "Map plot generation failed. Inspect logs above."; exit 130;
}

echo "== Reproduction pipeline finished successfully =="
