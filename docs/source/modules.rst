Modules
=======

This page contains the API documentation extracted from docstrings for all modules in the **reprod** project (under the ``/reprod/src`` directory).

.. contents::
   :local:
   :depth: 3


Pipelines
---------

Add Alzheimer Pathology: ``add_alzheimer_pathology``

.. automodule:: src.pipelines.add_alzheimer_pathology
   :members:
   :undoc-members:
   :show-inheritance:

Add ARUK-UCL Bioprocesses to Neo4j: ``add_arukucl_bioprocesses_to_neo4j``

.. automodule:: src.pipelines.add_arukucl_bioprocesses_to_neo4j
   :members:
   :undoc-members:
   :show-inheritance:

  Add DrugBank to Neo4j: ``add_drugbank2neo4j``

.. automodule:: src.pipelines.add_drugbank2neo4j
   :members:
   :undoc-members:
   :show-inheritance:

  Connect Bioprocess with Drug: ``connect_bioprocess_with_drug``

.. automodule:: src.pipelines.connect_bioprocess_with_drug
   :members:
   :undoc-members:
   :show-inheritance:

  Export Drug and Process CSVs: ``export_drug_and_process_csvs``

.. automodule:: src.pipelines.export_drug_and_process_csvs
   :members:
   :undoc-members:
   :show-inheritance:

  Filter ARUK-UCL for Bio Process: ``filter_arukucl_for_bio_process``

.. automodule:: src.pipelines.filter_arukucl_for_bio_process
   :members:
   :undoc-members:
   :show-inheritance:

  Generate Top-100 and Top-30 for UMAP: ``generate_top_100_and_30_for_umap``

.. automodule:: src.pipelines.generate_top_100_and_30_for_umap
   :members:
   :undoc-members:
   :show-inheritance:

  Generate Zero-Shot Prompts: ``generate_zero_shot_prompts``

.. automodule:: src.pipelines.generate_zero_shot_prompts
   :members:
   :undoc-members:
   :show-inheritance:

  Get ClinicalTrials.gov Data: ``get_trialsgov_data``

.. automodule:: src.pipelines.get_trialsgov_data
   :members:
   :undoc-members:
   :show-inheritance:

  GO Drug Classification to LLM: ``GO_drug_classification2LLM``

.. automodule:: src.pipelines.GO_drug_classification2LLM
   :members:
   :undoc-members:
   :show-inheritance:

  Integrate Highly Rated GO Classification for Bio Process: ``integrate_highly_rated_GO_classification_for_bio_process``

.. automodule:: src.pipelines.integrate_highly_rated_GO_classification_for_bio_process
   :members:
   :undoc-members:
   :show-inheritance:

  Integrate Rating JSONs: ``integrate_rating_jsons``

.. automodule:: src.pipelines.integrate_rating_jsons
   :members:
   :undoc-members:
   :show-inheritance:

  Integrate Zero-Shot Ratings: ``integrate_zero_shot_ratings``

.. automodule:: src.pipelines.integrate_zero_shot_ratings
   :members:
   :undoc-members:
   :show-inheritance:

  JSON Prompt Generator for GO Classification: ``JSON_prompt_generator_GO_classification``

.. automodule:: src.pipelines.JSON_prompt_generator_GO_classification
   :members:
   :undoc-members:
   :show-inheritance:

  JSON Prompts to LLM: ``JSON_prompts2LLM``

.. automodule:: src.pipelines.JSON_prompts2LLM
   :members:
   :undoc-members:
   :show-inheritance:

  Map GO Terms for Drugs: ``map_go_terms_for_drugs``

.. automodule:: src.pipelines.map_go_terms_for_drugs
   :members:
   :undoc-members:
   :show-inheritance:

  Rating JSON Generator: ``rating_JSON_generator``

.. automodule:: src.pipelines.rating_JSON_generator
   :members:
   :undoc-members:
   :show-inheritance:

  Remove Island Drugs: ``remove_island_drugs``

.. automodule:: src.pipelines.remove_island_drugs
   :members:
   :undoc-members:
   :show-inheritance:


Statistics
----------

  Calculate Closest Approach: ``calculate_closest_approach``

.. automodule:: src.statistics.calculate_closest_approach
   :members:
   :undoc-members:
   :show-inheritance:

  Export Top-Rated Nodes: ``export_top_rated_nodes``

.. automodule:: src.statistics.export_top_rated_nodes
   :members:
   :undoc-members:
   :show-inheritance:

  Friedman Test on Ratings: ``friedman_test_on_ratings``

.. automodule:: src.statistics.friedman_test_on_ratings
   :members:
   :undoc-members:
   :show-inheritance:


Tests
-----

  Verify AD Drug and Bioprocess Counts: ``verify_ad_drug_and_bioprocess_counts``

.. automodule:: src.tests.verify_ad_drug_and_bioprocess_counts
   :members:
   :undoc-members:
   :show-inheritance:

  Verify Number of Drugs: ``verify_number_of_drugs``

.. automodule:: src.tests.verify_number_of_drugs
   :members:
   :undoc-members:
   :show-inheritance:


Utilities
---------

  Neo4j Connection Utilities: ``conn_neo4j``

.. automodule:: src.utils.conn_neo4j
   :members:
   :undoc-members:
   :show-inheritance:

  Logging Configuration: ``logging_config``

.. automodule:: src.utils.logging_config
   :members:
   :undoc-members:
   :show-inheritance:

  UUID Utilities: ``uuid_util``

.. automodule:: src.utils.uuid_util
   :members:
   :undoc-members:
   :show-inheritance:


Visualization
-------------

  GO Process Plot: ``GO_process_plot``

.. automodule:: src.visualization.GO_process_plot
   :members:
   :undoc-members:
   :show-inheritance:

  Map Plot: ``map_plot``

.. automodule:: src.visualization.map_plot
   :members:
   :undoc-members:
   :show-inheritance:

  Plot Rating Densities: ``plot_rating_densities``

.. automodule:: src.visualization.plot_rating_densities
   :members:
   :undoc-members:
   :show-inheritance:

  Plot Rating Distribution Positioned by Mean: ``plot_rating_distribution_positioned_by_mean``

.. automodule:: src.visualization.plot_rating_distribution_positioned_by_mean
   :members:
   :undoc-members:
   :show-inheritance:

  Plot Top-20 Rating Distributions: ``plot_top20_rating_distributions``

.. automodule:: src.visualization.plot_top20_rating_distributions
   :members:
   :undoc-members:
   :show-inheritance:

  Ripretinib Bioprocess Graph: ``ripretinib_bioprocess_graph``

.. automodule:: src.visualization.ripretinib_bioprocess_graph
   :members:
   :undoc-members:
   :show-inheritance:

  Trial Scatterplot: ``trial_scatterplot``

.. automodule:: src.visualization.trial_scatterplot
   :members:
   :undoc-members:
   :show-inheritance:

  UMAP Approaches Plot: ``umap_approaches_plot``

.. automodule:: src.visualization.umap_approaches_plot
   :members:
   :undoc-members:
   :show-inheritance:

  UMAP Top-30 Annotated: ``umap_top30_annotated``

.. automodule:: src.visualization.umap_top30_annotated
   :members:
   :undoc-members:
   :show-inheritance:

  UMAP Validation Plot: ``umap_validation_plot``

.. automodule:: src.visualization.umap_validation_plot
   :members:
   :undoc-members:
   :show-inheritance: