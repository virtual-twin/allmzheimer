
Properties and Relationships
====================================================

.. contents:: 
    :local:
    :depth: 4


This page provides an overview of the nodes and types of relationships present in the Neo4j database.


.. figure:: /_static/media/protein_drug_process_pathology.png
   :alt: Graph containing biological processes, proteins, drugs and the pathology Alzheimer's
   :width: 1000px
   :align: center

   Graph containing biological processes, proteins, drugs and the pathology Alzheimer's.
   (Click on the image to view it full screen or to download it)


Node Types
---------------------------------------------------------------

The database contains the following types of nodes, defined by their labels:

- **BiologicalProcess**
- **Protein**
- **Pathology**
- **Drug**


BiologicalProcess
--------------------------------------------------------------------

**BiologicalProcess** nodes represent biological processes from the Gene Ontology.
Currently (20.05.24), these nodes originate only from the ARUK-UCL selection of Alzheimer's-relevant biological processes.
Possibly, this selection will be completed by also including biological processes from the Alzheimer Ontology (ADO) and the Alzheimer GO selection by the University of Toronto.
They are added to the db in the `add_arukuclprocess2neo4j.py` script.

**BiologicalProcess** nodes have the following properties that are depicted with an example:




- **<elementId>**: 4:b40f48b9-734d-419a-9c77-dadbfe86adf1:7
- **<id>**: 7
- **annotationExtension**: NaN
- **assignedBy**: ARUK-UCL
- **ecoId**: ECO:0000315
- **geneProductDb**: UniProtKB
- **geneProductId**: Q8NA29
- **goAspect**: P
- **goEvidenceCode**: IMP
- **goName**: lysophospholipid translocation
- **goTerm**: GO:0140329
- **label**: lysophospholipid translocation
- **qualifier**: involved_in
- **reference**: PMID:26005865
- **symbol**: MFSD2A
- **taxonId**: 9606
- **uuid**: 34d00df7-039e-4151-b31d-bee7d47a0379
- **withFrom**: NaN




Protein
---------------------------------------------------------------------------

**Protein** nodes represent proteins from the UniProt database.
The protein nodes in the Neo4j database are a subset of proteins contained in the ARUK-UCL Alzheimer's selection of biological processes and proteins.
They are added to the db in the `add_UniProt2bioprocessneo4j.py` script.

**Protein** nodes have the following properties depicted with an example:


- **<elementId>**: 4:b40f48b9-734d-419a-9c77-dadbfe86adf1:369
- **<id>**: 369
- **accession**: A0A0G2JXN2
- **function**: Microtubule-associated protein that is involved in the formation of parallel microtubule bundles linked by cross-bridges in the proximal axon. Required for the uniform orientation and maintenance of the parallel microtubule fascicles, which are important for efficient cargo delivery and trafficking in axons. Thereby also required for proper axon specification, the establishment of neuronal polarity and proper neuronal migration
- **geneName**: N/A
- **organism**: Rattus norvegicus
- **proteinName**: Tripartite motif-containing protein 46
- **subcellularLocation**: Cell projection, axon
- **uuid**: d9894590-a16a-471b-8c3d-47d0473e5f47

.. figure:: /_static/media/protein_process_pathology_graph.png
   :alt: Graph containing biological processes and proteins
   :width: 1000px
   :align: center

   Graph containing biological processes and proteins
   (Click on the image to view it full screen or to download it)

Pathology
-----------------------------------------------------------------------------------------------

**Pathology** nodes represent pathologies in the neo4j database. 
For the allmzheimer project, there is just one 'Alzheimer's' node present.
Due to the possible issues coming along with using an apostrophe in a node name, the node is simply called 'Alzheimer'.

**Pathology** nodes have the following properties depicted with an example:

- **<elementId>**: 4:b40f48b9-734d-419a-9c77-dadbfe86adf1:368
- **<id>**: 368
- **pathologyName**: Alzheimer
- **uuid**: 001f9418-b4a7-43f5-ba49-72ba4a549f3d


Drug 
----------------------------------------------------------------------------------------------

**Drug** nodes represent drugs listed in the DrugBank which kindly allowed the usage of their database for this project.
All drugs in the drugbank were added to the neo4j-database. Then they should be connected with the **BiologicalProcess** nodes.
This connection should be made, if a drug has an effect on a biological process.
However, currently (20.05.24) this connection does not work. 
Resolving this issue may require a thorough review of the existing properties.

**Drug** nodes have the following properties depicted with an example:



- **<elementId>**: 4:b40f48b9-734d-419a-9c77-dadbfe86adf1:381
- **<id>**: 381
- **affectedGoProcess**: integral component of plasma membrane,intracellular,plasma membrane,type I interferon receptor activity,cell surface receptor signaling pathway,cytokine-mediated signaling pathway ...
- **affectedGoProcessId**: GO:0005886,GO:0061824,GO:0005886,GO:0004905,GO:0007166,GO:0019221 ...
- **clinicalDescription**: 
- **description**: Interferon alfa-n1 consists of purified, natural (n is for natural) alpha interferon subtypes, at least two of which are glycosylated. This differs from recombinant alpha interferons, which are individual non-glycosylated proteins produced from individual alpha interferon genes.
- **drugbankId**: DB00011
- **indication**: For the treatment of venereal or genital warts caused by the Human Papiloma Virus.
- **mechanismOfAction**: Interferon alpha binds to type I interferon receptors (IFNAR1 and IFNAR2c) which, upon dimerization, activate two Jak (Janus kinase) tyrosine kinases (Jak1 and Tyk2). These transphosphorylate themselves and phosphorylate the receptors. The phosphorylated INFAR receptors then bind to Stat1 and Stat2 (signal transducers and activators of transcription)which dimerize and activate multiple (~100) immunomodulatory and antiviral proteins. Interferon alpha binds less stably to type I interferon receptors than interferon beta.
- **name**: Interferon alfa-n1
- **pharmacodynamics**: Upregulates the expression of MHC I proteins, allowing for increased presentation of peptides derived from viral antigens. This enhances the activation of CD8+ T cells that are the precursors for cytotoxic T lymphocytes (CTLs) and makes the macrophage a better target for CTL-mediated killing. Interferon alpha also induce the synthesis of several key antiviral mediators, including 2'-5' oligoadenylate synthetase (2'-5' A synthetase) and protein kinase R.
- **promising**: true
- **reason**: The drug appears to have a specific impact on biological processes related to Alzheimer's disease, such as defense response to virus and cytokine-mediated signaling pathway. These processes are known to be involved in the development and progression of Alzheimer's disease. The drug's ability to modulate these pathways could potentially lead to new therapeutic approaches for treating Alzheimer's.
- **simpleDescription**: 
- **therapeuticallySignificant**: 


.. figure:: /_static/media/drug_and_relations.png
   :alt: Graph containing drugs and corresponding biological processes
   :width: 1000px
   :align: center

   Graph containing drugs and corresponding biological processes
   (Click on the image to view it full screen or to download it)





Types of Relationships
---------------------------------------------------------------

There are currently three types of relationships in the database:

- **ASSOCIATED_WITH**: Stemming from `add_UniProt2bioprocessneo4j`, this relationship indicates that a protein is associated with a biological process.
- **RELATED_TO**: Originating from `add_pathology2neo4j.py`, this relationship means that a biological process is related to a pathology (specifically Alzheimer's in this context).
- **AFFECTS**: Coming from `add_process2drug.py`, this relationship implies that a drug affects a biological process. However, this connection is not yet well established as of 20.05.24.

.. figure:: /_static/media/associated_with_png.png
   :alt: Graph depicting 'ASSOCIATED_WITH' Relationship
   :width: 1000px
   :align: center

   Graph depicting 'ASSOCIATED_WITH' Relationship
   (Click on the image to view it full screen or to download it)

Retrieving Relationship Types
---------------------------------------------------------------

Use the following Cypher query to retrieve all unique relationship types in the database:

.. code-block:: cypher

    MATCH ()-[r]->()
    RETURN DISTINCT type(r) AS RelationshipType

Expected Output:
"ASSOCIATED_WITH"
"RELATED_TO"
"AFFECTS" 


Relationship Properties
---------------------------------------------------------------

Biological process nodes have the following properties:

Retrieving Biological Processes, Proteins, Drugs, Pathology
---------------------------------------------------------------

Use the following Cypher query to retrieve BiologicalProcess

.. code-block:: cypher

    MATCH (b: BiologicalProcess)
    RETURN b
    LIMIT 10

Replace 'b' and 'BiologicalProcess' with:

- p: Protein for Protein
- d: Drug for Drugs
- p: Pathology for Pathology



The following commands are for resetting the outputs of the LLM for testing purposes - use them with caution! 

Reset the 'reason' property in db
--------------------------------------------------------------------


.. code-block:: cypher

   MATCH (n)
   WHERE n.reason IS NOT NULL
   REMOVE n.reason
   RETURN COUNT(n)


Reset the 'promising' property in db
--------------------------------------------------------------------


.. code-block:: cypher

   MATCH (n)
   WHERE n.promising IS NOT NULL
   REMOVE n.promising
   RETURN COUNT(n)

Reset the prompt_token_length in db 
--------------------------------------------------------------------


.. code-block:: cypher

   MATCH (n)
   WHERE n.prompt_token_length IS NOT NULL
   REMOVE n.prompt_token_length
   RETURN COUNT(n)