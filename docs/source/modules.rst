Modules
=======

This page contains the documentation of each module of the **allmzheimer** pipeline. Properties and relationships of each node are described in :doc:`propertiesandrelationships`.

.. contents::
   :local:
   :depth: 4


Dataset Preparation
-------------------
### Filter ARUK-UCL for Bio Process: `filter_arukucl_for_bioprocess`

.. automodule:: src_pub.dataset_prep.filter_arukucl_for_bioprocess
    :members:
    :undoc-members:
    :show-inheritance:

Database Entry
--------------
### Add ARUK-UCL Process to Neo4j: `add_arukuclprocess2neo4j`

.. automodule:: src_pub.db_entry.add_arukuclprocess2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

### Add DrugBank to Neo4j: `add_drugbank2neo4j`

.. automodule:: src_pub.db_entry.add_drugbank2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

### Add Pathology to Neo4j: `add_pathology2neo4j`

.. automodule:: src_pub.db_entry.add_pathology2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

### Connect BioProcess with Drug: `connect_bioprocess_with_drug`

.. automodule:: src_pub.db_entry.connect_bioprocess_with_drug
    :members:
    :undoc-members:
    :show-inheritance:

### Monitor Drug Process Connecting: `monitor_drug_process_connecting`

.. automodule:: src_pub.db_entry.monitor_drug_process_connecting
    :members:
    :undoc-members:
    :show-inheritance:

DB Filter
---------
### Remove Island Drugs: `rm_island_drugs`

.. automodule:: src_pub.db_filter.rm_island_drugs
    :members:
    :undoc-members:
    :show-inheritance:

Explore DB
----------
### Query DB for Alzheimer's Drugs: `query_db_for_alz_drugs`

.. automodule:: src_pub.explore_db.query_db_for_alz_drugs
    :members:
    :undoc-members:
    :show-inheritance:

### Query DB for Alzheimer's Processes: `query_db_for_alzheimer_proesses`

.. automodule:: src_pub.explore_db.query_db_for_alzheimer_proesses
    :members:
    :undoc-members:
    :show-inheritance:

### Query DB for Non-Alzheimer's Drugs: `query_db_for_non_alz_drugs`

.. automodule:: src_pub.explore_db.query_db_for_non_alz_drugs
    :members:
    :undoc-members:
    :show-inheritance:

Gene Ontology Data
-------------------
### GO Term Mapping: `GO_term_mapping`

.. automodule:: src_pub.gene_ontology_data.GO_term_mapping
    :members:
    :undoc-members:
    :show-inheritance:

### Monitor GO Term Mapping: `monitor_go_term_mapping`

.. automodule:: src_pub.gene_ontology_data.monitor_go_term_mapping
    :members:
    :undoc-members:
    :show-inheritance:


LLM Rating
----------
### Create Prompts: `rating_JSON_generator`

.. automodule:: src_pub.LLM_rating.create_prompts.rating_JSON_generator
    :members:
    :undoc-members:
    :show-inheritance:

### Integrate Prompts: `integrate_rating_jsons`

.. automodule:: src_pub.LLM_rating.integrate_prompts.integrate_rating_jsons
    :members:
    :undoc-members:
    :show-inheritance:

### Provide Prompts to LLM: `JSON_prompts2LLM`

.. automodule:: src_pub.LLM_rating.provide_prompts2LLM.JSON_prompts2LLM
    :members:
    :undoc-members:
    :show-inheritance:

Utils
-----
### Danger Reset DB: `DANGER_reset_db`

.. automodule:: src_pub.utils.DANGER_reset_db
    :members:
    :undoc-members:
    :show-inheritance:

### Neo4j Connection: `conn_neo4j`

.. automodule:: src_pub.utils.conn_neo4j
    :members:
    :undoc-members:
    :show-inheritance:

### Logging Configuration: `logging_config`

.. automodule:: src_pub.utils.logging_config
    :members:
    :undoc-members:
    :show-inheritance:

### UUID Utility: `uuid_util`

.. automodule:: src_pub.utils.uuid_util
    :members:
    :undoc-members:
    :show-inheritance:

Clinical Trials
---------------
### Get Trials.gov Data: `get_trialsgov_data`

.. automodule:: src_pub.clinical_trials.get_trialsgov_data
    :members:
    :undoc-members:
    :show-inheritance:



