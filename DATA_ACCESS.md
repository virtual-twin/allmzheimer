
## Drugbank Dataset
You may apply for an academic license of the Drugbank here: https://www.drugbank.com/academic_research
Once you have that dataset as an XML (version 5.1.12 was used for the research done in this repository) you can reproduce the graph database we established as described in the research paper.


## ARUK-UCL-GO terms
The Alzheimer's associated GO terms curated by the ARUK-UCL research group can be downloaded as .csv here: https://www.ebi.ac.uk/QuickGO/annotations?assignedBy=ARUK-UCL
This dataset includes 15,610 annotations. Please run this file on it to filter for biological processes and unique terms: src/2_dataset_prep/filter_arukucl_for_bio_process.py
After having run filter_arukucl_for_bio_process.py on the csv, you may proceed to create a graph database based on these terms.

