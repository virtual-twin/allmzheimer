Background
================

This Python package accompanies the paper 'Biological database mining for LLM-driven Alzheimer’s Disease Drug Repurposing' which provides detailed explanation of the methods.
Therefore, this background-page is meant as a brief introduction.
Generally, the allmzheimer project is about leveraging AI assisted drug repurposing by employing the structured knowledge of ontologies.
This structured knowledge may then be provided (using the functions from this package) to a large lanugage model which performs drug repuporposing evaluation on the knowledge retrieved.


The following strcutured knowledge bases were connected:

- **Gene Ontology**
- **DrugBank**

Each of these knowledge bases provide domaine relevant knowledge that allows to gain insights from the interplay of these resources.


.. image:: /_static/media/ripretinib_v9.png
   :alt: Relationship of ontologies
   :width: 400px
   :align: center

As depicted on the sample graph there is a graph database that contains nodes for drugs (purple), biological processes (green), pathology (blue).

The specific information contained in each node is described in :doc:`propertiesandrelationships`.

The Neo4j graph database serves as basis for prompting the LLM with specific requests for identifiying drugs that may be investigated for their potential on treating Alzheimer's disease.
You find specific information on how the prompt is designed in :doc:`modules`.


This codebase assumes the usage of 'Ollama' and llama3 as large language model. 
However, the code may be easily adjusted to employ different models.

Please refer to the original preprint (https://doi.org/10.1101/2024.12.04.626255) and its supplementary documents for detailed descriptions of the background.