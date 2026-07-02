import json
import boto3
import uuid
from urllib.parse import urlparse
from pathlib import Path

ba = boto3.client("bedrock-agent", region_name="ap-southeast-1")
kb_id = "SI1PK19NAO"
ds = "2P9F3GBINS"
random_uuid = uuid.uuid4()


def lambda_handler(event, context):
    print("THIS IS CLARVO SYNC")

    response = ba.start_ingestion_job(knowledgeBaseId=kb_id,
                                      dataSourceId=ds,
                                      clientToken=str(random_uuid),
                                      description='To sync knowledge source with the latest document uploaded or deleted in S3.')

    print(f"RESPONSE: {response["ingestionJob"]}")

    return {"status": 200,
            "data": {
                "knowledgeBaseId": response["ingestionJob"]["knowledgeBaseId"],
                "dataSourceId": response["ingestionJob"]["dataSourceId"],
                "ingestionJobId": response["ingestionJob"]["ingestionJobId"],
                "description": response["ingestionJob"]["description"],
                "status": response["ingestionJob"]["status"]
            }}
