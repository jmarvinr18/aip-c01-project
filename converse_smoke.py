import boto3, sys, time, random
from botocore.exceptions import ClientError

REGION = "ap-southeast-1"


MODELS = {
    "Nova Lite": {
        "modelId": "global.amazon.nova-2-lite-v1:0",
        "inferenceConfig": {"maxTokens": 200, "temperature": 0.3, "topP": 0.9},
    },
    "Claude Haiku": {
        "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "inferenceConfig": {"maxTokens": 200, "temperature": 0.3},
    },
}

PROMPT = "In one sentence, what is Retrieval-Augmented Generation?"

def converse_stream(
    model_cfg: dict[str, object],
    region: str = REGION,
    max_retries: int = 5,
) -> str:
    """
    Stream a response from Amazon Bedrock using the Converse Stream API.

    Args:
        model_cfg: Model config dict with 'modelId' and 'inferenceConfig' keys.
        region: AWS region for the Bedrock Runtime endpoint.
        max_retries: Maximum number of retry attempts on ThrottlingException.

    Returns:
        The full response text assembled from streamed chunks.

    Raises:
        ClientError: For any non-throttling Bedrock API error, or when retries
            are exhausted.
    """
    client = boto3.client("bedrock-runtime", region_name=region)
    for attempt in range(max_retries):
        try:
            resp = client.converse_stream(
                modelId=model_cfg["modelId"],
                messages=[{"role": "user", "content": [{"text": PROMPT}]}],
                inferenceConfig=model_cfg["inferenceConfig"],
            )
            chunks: list[str] = []
            for event in resp["stream"]:
                if "contentBlockDelta" in event:
                    chunks.append(event["contentBlockDelta"]["delta"]["text"])
            return "".join(chunks)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ThrottlingException" and attempt < max_retries - 1:
                time.sleep((2 ** attempt) + random.uniform(0, 1))
            else:
                raise

ok: bool = True

for name, cfg in MODELS.items():
    try:
        print(f"\n=== {name} ({cfg['modelId']}) ===")
        print(converse_stream(cfg).strip())

    except ClientError as e:
        ok = False
        code = e.response["Error"]["Code"]
        print(f" X {code}: {e.response['Error']['Message']}")

sys.exit(0 if ok else 1)
