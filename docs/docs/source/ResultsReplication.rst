Results Replication
===============================================

Order of scripts to be run
---------------------------------------------------------------------------

# Adding data 
add_arukuclprocess2neo4j.py
add_drugbank2neo4j.py
update_additional
update_additionaldrugbankvaluesinneo4j.py # this is for the drug classification
add_pathology2neo4j.py
GO_term_mapping.py # run monitor_mapping.py in parallel for monitoring
connect_bioprocess_with_drug.py # run monitor_drug_process_connecting.py in parallel for monitoring

# Filtering data
remove_island_drugs.py

# Llama setup
JSON_prompt_generator.py
JSONdrug2LLM.py
integrate_cluster_jsons.py

# Script used for the first succesful implementation of the cluster
/Users/ricoandreschmitt/Code/GitHub/cluster_allmzheimer/JSON_prompt_generator.py # - this script contained the 0.01 rating
# The results of these runs are generally stored here:
/Users/ricoandreschmitt/Code/GitHub/cluster_allmzheimer


# Figures
/tests/plot_rating.ipynb


This page provides cypher code for queries to replicate all results from the paper.

Total number of added proteins
----------------------------------------------------------------------------
.. code-block:: cypher
    MATCH (p: Protein)
    RETURN COUNT (p)

Expected result:
**1412**

Total number of unique biological processes added
----------------------------------------------------------------------------
.. code-block:: cypher 
    MATCH (b: BiologicalProcess)
    RETURN COUNT (b)

Expected result:
**1778**

Please note:
If you just import the biological processes and proteins from the ARUKU-UCL dataset and create a node for each row the number of BiologicalProcess and Protein nodes will be higher.
Specifically, you will get these numbers:
BiologicalProcess count: 8780
Protein count: 1757

However, there are only 1778 unique biological processes. 
In the Gene Product column of the ARUKU-UCL dataset there are 1757 unique values. However, only 1414 of them are valid UniProt proteins. 
There are 364 ComplexPortal entities which were ignored. Moreover, when fetching the proteins from the ARUK-UCL dataset to UniProt (28.05.2024) there were two API errors because the UniProt ID was not connected with data.
So here is a summary how 1412 protein nodes are created:
1412 + 2 + 343 = 1757
Included protein nodes + Failed API requests + ComplexPortal = Total number in ARUK-UCL dataset

Drugs from the Drugbank that have Alzheimer's as an indication
----------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d:Drug)
    WHERE toLower(d.indication) CONTAINS 'alzheim'
    RETURN COUNT(d)
    
Result:
-------

43


Drugs for Repurposing - No Alzheimer's indication
----------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d:Drug)
    WHERE NOT toLower(d.indication) CONTAINS 'alzheim' OR d.indication IS NULL OR d.indication = ''
    RETURN COUNT(d)
    
Result:
-------

5592


Total drug nodes that are connected to biological processes and therefore remained in the database
----------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d : Drug)
    RETURN COUNT(d)
    
Result:
-------

5635


Check of numbers
--------------------

Drugs with Alzheimer's indication + Drugs without Alzheimer's == Total number of drugs
--------------------------------------------------------------------------------------

Is that the case?

.. code-block:: text

    43 + 5592 == 5635
    
Result:
-------

TRUE


Check specific drug nodes
----------------------------------------------------------------------------------------

.. code-block:: text

    MATCH (n {name: "Aducanumab"})
    RETURN n.name, n.promising, n.reason


Total number of recommendations

Total number of added proteins
----------------------------------------------------------------------------
.. code-block:: cypher
    MATCH (p: Protein)
    RETURN COUNT (p)

cliniclatrials.gov
------------------------------------------------------------------------------------------
2918 of the drugs have studies associated with them (first run - results not replicated yet) 