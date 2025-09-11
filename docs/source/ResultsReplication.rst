Reproduction of Results
=======

The complete reproduction pipeline is provided in the reprod/ directory.
It runs all methods and regenerates every result (plots, statistics, database entries, prompts) inside a containerized environment.
The pipeline reproduces results with current external data sources (e.g. GeneOntology, ClinicalTrials.gov). Minor deviations from the published manuscript may occur but are checked automatically for reasonable margins.

For transparency, Jupyter notebooks in plot_creation_pub/, src_pub/, statistics_pub/, and tests_pub/ document the outputs we obtained when preparing the manuscript. These complement, but do not replace, the containerized pipeline.

Docker compose setup
-----
To standardize the environment we provide to researchers using our code, we have decided to provide a containerized pipeline. 
Within in this pipeline, the code runs on predefined versions (requirements.txt) and processes the data stored in /reprod/datasets (unless you change the dataset paths by making use of the .env).


To get started in the code:
	•	Read reprod/README.md for instructions on running the Docker setup.
	•	Read reprod/datasets/README_datasets.md for guidance on obtaining the required datasets.

