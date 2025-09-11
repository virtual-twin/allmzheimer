# allmzheimer

## Concept
This repository is dedicated to in silico drug development selection for Alzheimer's treatment and accompanies the paper 'Biological database mining for LLM-driven Alzheimer’s Disease Drug Repurposing' (BioRxiv DOI: https://doi.org/10.1101/2024.12.04.626255).

## Reproducibility
The entire project is conceptualized to support seamless reproducibility and utilization of the pipeline for new research. Therefore, the full code and the data necessary to reproduce the results are shared or made accessible.
Our containerized reproduction pipeline is designed to transparently reproduce all plots, database setups, datasets, ratings, statistical tests and other numbers reported.
For reproduction of the results go to the /reprod directory and read reprod/README.md (explaining all steps and requirements) and reprod/datasets/README_datasets.md (explaining how to attain the data for reproducing the results).

## Reporting of results
The directories plot_creation_pub, src_pub and statistics_pub contain jupyter notebooks to document the output we saw when we produced the results reported in the paper. While jupyter notebooks are great for documenting the code one has run, they often cause issues when trying to reproduce results (https://academic.oup.com/gigascience/article/doi/10.1093/gigascience/giad113/7516267). We therefore make use of both technologies. We provide you with the jupyter notebooks in the mentioned directories, so you can exactly see what we saw when we got to our results. The code in plot_creation_pub, src_pub and statistics_pub is mostly identical to the code in the /reprod directory (which allows it to run in the containerized environment). It is not meant to document.
But you also get a complete containerized reproduction pipeline (in reprod) which is supposed to reproduce all results (updated with the most current data from the external APIs) without manual intervention.

## Deviations from reported results in reproduction pipeline
Since the external APIs (GeneOntology, Clinical Trials gov) change over time, you will see slightly different results when running the pipeline. However, these differences are expected to be within reasonable margin (e.g. if 0.5% of the GO-term mappings change after two years, this might be reasonable, if you get <10% different mappings there is most likely an issue). The code checks for such deviations (reprod/src/tests) and warns if they are within reasonable margins (so you can decide yourself if this is reasonable or not) and logs errors if there are major differences.
Also some plots in the manuscript were slightly edited to enhance readability (never to change actual content). We describe in the code where this was the case. However, these layout adjustments should never change anything about the result of the plot and therefore, the reproduced plots reproduced are expected to be in alignment with the reported results.

## Documentation
Extensive documentation is available (TO DO: host HTML once public) at URL.
(Currently the documentation can be achieved by running 'make html' in root/docs with a venv that has Sphinx installed)



# Repository Orientation
Please find a short description of the modules and directories below:

reprod
------------------------------------
Directory containing the drug repurposing pipeline that can be used to reproduce results or to utilize the pipeline for new research.


docs
------------------------------------
This directory contains the documentation files that allow you to read this page.

plot_creation_pub
------------------------------------
Here, you find the code that ran to produce the visualizations in the paper and the supplementary documents. 


src_pub
------------------------------------
This directory contains all source code that was used for the paper.


statistics_pub
------------------------------------
This directory contains the files that were associated with the Friedman-Test conducted in the paper.

tests_pub
------------------------------------
Here, you find the Jupyter Notebook reporting the token length analysis that was done for each rating prompt the Large Language Model was provided with to check compliance with the context window of the model.



## Getting Started

go to the reprod directory

## Contributing
Contributions are welcome! Please fork the repository and use a feature branch.
We highly recommend to make code changes in the /reprod directory as this directory contains the code that can be easily utilized for future projects.
Pull requests are reviewed actively.


## Declaration of generative AI use for coding
GitHub Copilot and Chat-GPT were used for formatting, debugging and coding assistance in this project.
This does not affect the full responsibility of the authors for all code, documentation, results and reporting.


## Maintainers
This repository is maintained by:
- [Rico Schmitt](https://github.com/RicoSchmitt)
- [Petra Ritter](https://github.com/Petra-Ritter)
- [Brain Simulation Section at Charité](https://github.com/brainmodes) (head: Prof. Petra Ritter)

## Contact
If you have any questions or issues, please open an issue on this repository or contact us at [petra.ritter@charite.de] .

# License
This repository is published under the open source EUPL-1.2 license. Please refer to LICENSE.md and the [EUPL-1.2](https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12) webpage for further details.
