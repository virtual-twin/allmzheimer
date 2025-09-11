# file: src/pipelines/generate_zero_shot_prompts.py
import os
import json
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv
import tiktoken

# Project logging 
try:
    from src.utils.logging_config import setup_logging  # noqa
    _use_custom_logging = True
except Exception:
    _use_custom_logging = False


load_dotenv()

logger = logging.getLogger(__name__)

MANDATORY_FORM = """
Remember, only about 0.01 percent of the drugs you assess will be selected for further testing for Alzheimer's disease drug repurposing.
You have to base your reason on the information you have on the drug.
This is the mandatory form for your JSON output:

"{\n"
'   "reason_rating": "your reason here"\n'
'   "rating": number from 0 to 1,\n'  
"}"
Do only provide this particular valid json format at any cost.
"""

intro = """ 
You are a careful pharmaceutical scientist responsible for selecting drugs to repurpose for Alzheimer's disease.
You have strictly limited resources and can only select the most promising drugs.
You need to rate the drug on a scale from 0 to 1 to classify how promising you consider the repurposing of the drug to be based on careful assessment.
The higher the number (1 at max), the more promising you will consider the drug.

Provide your reasoning in 'reason_rating' in your JSON output.

This is the mandatory form for your JSON output:
"{\n"
'   "reason_rating": "your reason here"\n'
'   "rating": number from 0 to 1,\n'  
"}"

Follow these instructions and always provide your response as JSON in this format.
"""

def calculate_token_length(prompt: str) -> int:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(prompt)
    return len(tokens)

def generate_prompt(drug_name: str) -> str:
    prompt = intro
    prompt += f"Drug name: {drug_name}\n\n"
    prompt += MANDATORY_FORM
    return prompt

def fetch_drug_names(uri: str, user: str, password: str):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    drugs = []
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (d:Drug) RETURN d.name AS name, d.drugbankId AS drugbankId"
            )
            drugs = [
                {"name": rec["name"], "drugbankId": rec["drugbankId"]}
                for rec in result
                if rec["name"]
            ]
            logger.info("Retrieved %d drugs from Neo4j.", len(drugs))
    except Exception as e:
        logger.error("Failed to fetch drugs: %s", e)
    finally:
        driver.close()
    return drugs

def main():

    if _use_custom_logging:
        setup_logging()
    else:
        logging.basicConfig(level=logging.INFO)

    uri = os.getenv("uri")
    user = os.getenv("username")
    password = os.getenv("password")

    # Allow override via env; default to container path
    output_dir = os.getenv(
        "ZERO_SHOT_PROMPTS_DIR",
        "/app/exports/prompts/zero_shot_prompts"
    )
    os.makedirs(output_dir, exist_ok=True)
    logger.info("Zero-shot prompts will be written to: %s", output_dir)

    drugs = fetch_drug_names(uri, user, password)
    written = 0

    for drug in drugs:
        prompt = generate_prompt(drug["name"])
        token_length = calculate_token_length(prompt)

        file_path = os.path.join(output_dir, f"{drug['drugbankId']}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "drugbankId": drug["drugbankId"],
                        "name": drug["name"],
                        "prompt": prompt,
                        "token_length": token_length,
                    },
                    f,
                    indent=4,
                    ensure_ascii=False,
                )
            written += 1
        except Exception as e:
            logger.error("Failed writing prompt for %s (%s): %s",
                         drug["name"], drug["drugbankId"], e)

    logger.info("Zero-shot prompt generation complete. Files written: %d", written)

if __name__ == "__main__":
    main()