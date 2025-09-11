# README_datasets directory
This directory is meant to store the datasets for reproducing the results.
While you can parse the datasets from any path to the scripts, it is most comfortable storing them in this directory.
We propose storing the following files here:

## Datasets 

### ARUK-UCL Gene Ontology Terms
Proposed path for the dataset (to work with default paths in pipeline):

reprod/datasets/ARUK-UCL-GO-terms.tsv

Download it from: https://www.ebi.ac.uk/QuickGO/annotations?assignedBy=ARUK-UCL


### Drugbank
Proposed path for the dataset (to work with default paths in pipeline):

reprod/datasets/drugbank_full_dataset.xml

Apply for the free academic license here: https://www.drugbank.com/academic_research and download the drugbank_full_dataset.xml
While the pipeline works by simply dropping this dataset in the datasets directory, this documentation might be useful to you: https://docs.drugbank.com/xml/#introduction
The drugbank version used for this paper is version 5.1.12, released on 2024-03-14. You may use other releases but will possibly get slighlty different results from using a different dataset.

### llm_outputs
If you setup the ARUK-UCL and DrugBank datasets you have everything you need for reproducing all results of the paper (the results would differ to some degree due to probabilistic elements of the LLM and updates to the external APIs that we utilize). 
However, this would require you to run all LLM-rating steps on your (perhaps local) machine. We therefore made the outputs of our llm-rating steps publicly available (GIGADB during review).
You can move the following directories in the llm_outputs directory to skip step 12 and 20 (LLM ratings) of the entrypoint.sh pipeline and to achieve the consecutive steps with our data:

reprod/llm_outputs/GO_classification_responses
reprod/llm_outputs/ontological_prompt_rating_outputs
reprod/llm_outputs/zeroshot_outputs

You can skip these steps by setting the 'RUN_LLM' variable in the .env to false (default).

We kept these directories consciously out of the /datasets directory as it is optional working with our data and you can generate it yourself (especially if you want to utilize this pipeline for your own purposes).



### Cummings et al Drug Repurposing Candidates
Please note that the file reprod/datasets/cummings_eta_al_AD_DR_candidates.json in the git repo is based on proposed drugs by Cummings et al in:

J. L. Cummings et al., “Drug repurposing for Alzheimer’s disease and other neurodegenerative disorders,” Nat. Commun., vol. 16, no. 1, p. 1755, Feb. 2025, doi: 10.1038/s41467-025-56690-4 

This list is used to compare our results with the literature and was not created by the authors of this paper and repository.