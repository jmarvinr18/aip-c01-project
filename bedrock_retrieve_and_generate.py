import boto3
import os
import json
from dotenv import load_dotenv

load_dotenv(".env_file")
# Access your variables safely
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")

client = boto3.client('bedrock-agent-runtime', region_name='ap-southeast-1')

response = client.retrieve_and_generate(
    input={
        'text': 'what is ai stages?'
    },
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': 'SI1PK19NAO',
            'modelArn': 'arn:aws:bedrock:ap-southeast-1:408897322877:inference-profile/apac.anthropic.claude-3-5-sonnet-20241022-v2:0'
        }
    }
)

# Print the final compiled response from the LLM
print(json.dumps(response))
