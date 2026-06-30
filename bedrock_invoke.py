import boto3
from botocore.exceptions import ClientError

MODEL_ID = "apac.anthropic.claude-haiku-4-5-20251001-v1:0"

client = boto3.client("bedrock-runtime", region_name="ap-southeast-1")


def invoke_claude(prompt: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
        )
        return response["output"]["message"]["content"][0]["text"]
    except ClientError as e:
        raise RuntimeError(f"Bedrock API error: {e.response['Error']['Message']}") from e


if __name__ == "__main__":
    print(invoke_claude("Hello, who are you?"))
