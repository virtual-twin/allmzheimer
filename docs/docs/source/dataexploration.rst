Purpose of this Page
======================
This page allows you to replicate the graph database creation described in the 'Methods' section of the 'Biological database mining for LLM-driven Alzheimer’s Disease Drug Repurposing' paper.
After you have run the code to create the database you may check the results with the Cyper commands below.



Data Exploration
======================


Drugs with Alzheimer's Disease indication:
----------------------------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d:Drug)
    WHERE toLower(d.indication) CONTAINS 'alzheim'
    RETURN COUNT(d)
    
Result:
-------

43


Drugs for Repurposing - No Alzheimer's indication
----------------------------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d:Drug)
    WHERE NOT toLower(d.indication) CONTAINS 'alzheim' OR d.indication IS NULL OR d.indication = ''
    RETURN COUNT(d)
    
Result:
----------------------------------------------------------------------------------------------

5592


Total drug nodes that are connected to biological processes
----------------------------------------------------------------------------------------------

.. code-block:: cypher

    MATCH (d : Drug)
    RETURN COUNT(d)
    
Result:
----------------------------------------------------------------------------------------------

5635


Check of numbers
----------------------------------------------------------------------------------------------

Drugs with Alzheimer's indication + Drugs without Alzheimer's == Total number of drugs
--------------------------------------------------------------------------------------

Is that the case?

.. code-block:: text

    43 + 5592 == 5635
    
Result:
-----------------------------------------------------------------------------------------------------

TRUE

Conclusion
----------------------------------------------------------------------------------------------

This shows that the selection criteria was correct, and that the number of rows of the CSVs fit.
