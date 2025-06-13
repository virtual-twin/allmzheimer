# allmzheimer

## Overview
This repository is dedicated to in silico drug development selection for Alzheimer's treatment and accompanies the paper 'Biological database mining for LLM-driven Alzheimer’s Disease Drug Repurposing' (BioRxiv DOI: https://doi.org/10.1101/2024.12.04.626255).
Please consult the docs that are also stored in this repository under /docs/build/html.
The documentation provides you with an overview of the technology used for achieving the results presented in the paper and gives you all the information to replicate the results or to employ the modules for your own purposes.

## Documentation
Extensive documentation is available (Host HTML once public - non-public during review) at URL.
(Currently the documentation can be achieved by running 'make html' in root/docs with a venv that has Sphinx installed)

## Reproducibility
The entire project is conceptualized to support seamless reproducibility. Therefore, the full code and the data necessary to reproduce the results should be shared (apart from the DrugBank, which requires licensing).

# Repository Orientation
Please find a short description of the modules and directories below:

docs
------------------------------------
This directory contains the documentation files that allow you to read this page.

plot_creation_pub
------------------------------------
Here, you find the code used for the visualizations in the paper and the supplementary documents.

src_pub
------------------------------------
This directory contains all code that was used for the paper. You may adjust it according to your needs to repurpose the code for other drug repurposing investigations (Please make sure to do that according to the CC BY NC 4.0 license provided in the repository).
Many modules are generalizable and can be used for a variety of tasks in which ontologies or graph databases should interact with Large Language Mdoels.

statistics_pub
------------------------------------
This directory contains the files that were associated with the Friedman-Test conducted in the paper.

tests_pub
------------------------------------
Here, you find the Jupyter Notebook reporting the token length analysis that was done for each rating prompt the Large Language Model was provided with to check compliance with the context window of the model.

.env_template
------------------------------------
Refer to this .env template to adjust it to your environment.

DATA_ACCESS.md
------------------------------------
Refer to these instructions to obtain the files needed to replicate the results from the paper.



## Getting Started


### Installation
1. Clone the repository:
    ```sh
    git clone https://github.com/RicoSchmitt/allmzheimer.git
    cd allmzheimer
    ```
2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

### Usage
Compare the documentation mentioned above.

### License
CC BY-NC 4.0

## Contributing
Contributions are welcome! Please fork the repository and use a feature branch. Pull requests are reviewed actively.
For a detailed description concerning contributions please refer to the HTML documentation.

## Declaration of generative AI use for coding
GitHub Copilot and Chat-GPT by OpenAi were used for coding assistance, formatting and debugging in this project.
This does not affect the full responsibility of the author for all code, documentation, results and reporting.


## Contact
If you have any questions or issues, please open an issue on this repository or contact us at [rico.schmitt@charite.de].

