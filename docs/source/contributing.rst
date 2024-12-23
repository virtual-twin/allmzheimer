Contributing
=================================

Thank you for visiting the contributing page.
Contributions - as code, raised concerns or additional thoughts - are welcome. 

Please raise an issue on `Github <https://github.com/RicoSchmitt/allmzheimer>`_ if you find a bug or have a suggestion for a new feature.

If you develop code on your own, please submit a pull request like this:

.. code-block:: Bash

    gh pr create --base main --head develop 
    --title "Merge develop into main" 
    --body "Please review the changes."

Adjust to your local branches and the content of your sumbission.

Current Branches
---------------------------------------------------
- **main**
- **develop**
- **property-name-alignment**



Branches Guideline
---------------------------------------------------
This repo follows the Gitflow workflow. 
This means there are the following branches:

1. **Main**
In short: Main should be used for releases only.
Contains production-ready code, that can be released. The branch can be tagged at commits to indicate different versions or releases. Other branches will be merged into the main branch after they have been tested.

2. **Develop**
Created at the start of the project. It should be maintained throughout the entire development process. It contains pre-production code with newly developed features while they are being tested.
Newly-created features should based off the develop branch, and then merged back when ready for testing.

3. **Feature**
Used when adding a new feature to the code. Start a feature branch off the develop branch and then merge the changes back into the develop branch once they are done.

4. **Release**
These branches should be used when preparing new releases. 
The administratotors of the allmzheimer-project will create releases and include your changes after your changes were successfully merged on the development branch.