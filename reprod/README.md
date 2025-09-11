### This file walks you through the full reproduction of results achieved by running a docker compose setup
The 'reprod' directory of this repo is concerned with reproducing ALL methods and results (all plots, all numbers, all entries in the db, all prompts) from the main script. 


entrypoint.sh runs the entire pipeline for reproducing all results within a containerized environment and starts automatically by executing:

```shell
docker compose build && docker compose up #from reprod directory
```
Before you start the docker compose you must set a .env file (copy example.env, adapt it as neeeded and store it as .env) and attain the (publicly available) datasets described in reprod/datasets/README_datasets.md. Make sure to read README_datasets.md as it explains the requirements for results reproduction in detail.


### Skipping local LLM rating steps
RUN_LLM is an .env variable that allows you to also run the LLM steps.
Iterations is an .env variable that allows you to control how many iterations there are.
While you can run the entire pipeline - with 10 iterations - as done in the original manuscript, we do not recommend doing this from a local machine.

However, if you run this pipeline on a local machine, we recommend leaving out the LLM rating iterations (or setting the iterations in the .env low) and make use of the data we provide (details in reprod/datasets/README_datasets.md). In our case, the iterations were run on a HPC cluster for several days to achieve all results.
But still, even with minimal computing power on a laptop all plots and results - apart from the rating iterations - can be reproduced with ease.

Also, if you decide to reproduce the results on such infrastructure, the docker-compose with the ollama container might not be a suitable solution.
The dockerized reproduction pipeline is made for making the reproduction of the results and the application of the software for new research as simple as possible.
However, if multiple iterations of the LLM steps are required, we recommend running ollama indpendently from this docker-compose setup (either on a GPU clusster or as external api) and changing the LLM_URL in .env to that source (e.g. externally hosted api or local LLM-API in local Kubernetes cluster or similar).

### Order of steps in the entrypoint.sh:
You may notice that the order of scripts and the generation of plots does not correspond with the order of figures in the manuscript.
This is on purpose as the entrypoint is ordered by computing complexity. Some of the steps require much more processing time (particularly those steps that fetch data from clinical trials.gov). Steps such as the UMAP processing also require much more resources and are more likely to have hardware specific issues.
While we tested all steps on multiple architectures and virtual machines, the embedding related steps have a higher risk of hardware related failures (different instruciton sets for x86 and amd of different generations). We therefore, put these steps at the very end, so in the unexpected case of them not working you still can reproduce most results without any manual debugging.
If you encounter such an issue, please raise an issue on github or contact us with your feedback. We tested the code on many machines but it is possible that there are architectures it does not run on.


