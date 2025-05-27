Modules
===================================

This page contains the documentation of each module of the allmzheimer pipeline.
Properties and relationships of each node are described in :doc:`propertiesandrelationships`.

.. contents:: 
    :local:
    :depth: 4


Dataset Preparation
---------------------------------------------------------------

Filter ARUK-UCL for Bio Process
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: 2_dataset_prep.filter_arukucl_for_bio_process
    :members:
    :undoc-members:
    :show-inheritance:

--------------------------------------------------------------------------------

Database Entry
------------------------------------------------------------------------------------------

Add ARUK-UCL Process to Neo4j
-----------------------------------------------------------------------------------------------------

.. automodule:: 3_db_entry.add_arukuclprocess2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

--------------------------------------------------------------------------------

Add ADO to Neo4j (currently not in use)
--------------------------------------------------------------------------------

.. automodule:: 3_db_entry.ado2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

Add UniProt to Bio Process Neo4j
--------------------------------------------------------------------------------------

.. automodule:: 3_db_entry.add_UniProt2bioprocessneo4j
    :members:
    :undoc-members:
    :show-inheritance:

----------------------------------------------------------------------------

Add Alzheimer's Disease Pathology to Neo4j
-------------------------------------------------------------------------------

.. automodule:: 3_db_entry.add_pathology2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

Retrieve additional information from Gene Ontology
--------------------------------------------------------------------------------------
.. automodule:: 3_db_entry.retrieve_GO_info
    :members:
    :undoc-members:
    :show-inheritance:

--------------------------------------------------------------------------------

Add drugs from DrugBank to Neo4j
--------------------------------
.. automodule:: 3_db_entry.add_drugbank2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

.. Outcommented files start upon html creation - this needs to be fixed in the scripts themselves

.. Connect bioprocess with drug
.. -------------------------------------------------------------------------------
.. .. automodule:: 3_db_entry.connect_bioprocess_with_drug
..     :members:
..     :undoc-members:
..     :show-inheritance:
--------------------------------------------------------------------------
.. Monitor Drug Processing connecting
.. ----------------------------------------------------------------------------
.. .. automodule:: 3_db_entry.monitor_drug_process_connecting
..     :members:
..     :undoc-members:
..     :show-inheritance:

.. GO term mapping
.. --------------------------------------------------------------------------------------
.. .. automodule:: 3_db_entry.GO_term_mapping
..     :members:
..     :undoc-members:
..     :show-inheritance:
.. ------------------------------------------------------------------------------

.. Monitor GO process mapping
.. -------------------------------------------------------------------------------
.. .. automodule:: 3_db_entry.monitor_mapping
..     :members:
..     :undoc-members:
..     :show-inheritance:



---------------------------------------------------------------------------
.. automodule:: 3_db_entry.add_arukuclprocess2neo4j
    :members:
    :undoc-members:
    :show-inheritance:

Retrieve Gene Ontology information
-----------------------------------------------------------------------------
.. automodule:: 3_db_entry.retrieve_GO_info
    :members:
    :undoc-members:
    :show-inheritance:


Utils
---------------------------------------------------------------

Here, you find the documentation for the util functions that are used throughout the pipeline.

Neo4j Connection
----------------------------------------------------------------------

.. automodule:: utils.conn_neo4j
    :members:
    :undoc-members:
    :show-inheritance:

Logging Configuration
---------------------------------------------------------------------------

.. automodule:: utils.logging_config
    :members:
    :undoc-members:
    :show-inheritance:


