import json
import boto3
import time
import uuid
from urllib.parse import urlparse
from pathlib import Path

ddb = boto3.client("dynamodb", region_name="ap-southeast-1")
s3 = boto3.client("s3", region_name="ap-southeast-1")
agent_rt = boto3.client("bedrock-agent-runtime", region_name="ap-southeast-1")
brt = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
MODEL = "apac.anthropic.claude-3-haiku-20240307-v1:0"
# session_id = str(uuid.uuid4())

TOOL_CONFIG = {
    "tools": [{
        "toolSpec": {
            "name": "search_documents",
            "description": """Always use search_documents before answering questions about documents. Search the company's document knowledge base for relevant passages. \
                Use this whenever the user asks about the contents of uploaded \
                documents, contracts, invoices or policies.""",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": """
                                A focused natural-language search query derived from the \
                                user's question.
                            """}
                },
                "required": ["query"]
            }}
        }
    }]
}


def search_documents(query: str, knowledge_base_id: str, num_results: int = 5):
    response = agent_rt.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"type": "TEXT", "text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": num_results
            }
        }
    )
    return [{
        "text": r["content"]["text"],
        "source": r["location"]["s3Location"]["uri"],
        "score": r.get("score")
    } for r in response["retrievalResults"]]


def ask(messages: str, knowledge_base_id: str, num_results: int = 5):

    # -- turn 1: model may request the tool --
    response = brt.converse(
        modelId=MODEL, messages=messages, toolConfig=TOOL_CONFIG)
    out = response["output"]["message"]

    messages.append(out)

    print(f"1ST RESPONSE: {json.dumps(response)}")

    if response["stopReason"] == "tool_use":
        tool_results = []
        for block in out["content"]:
            if "toolUse" in block:
                tu = block["toolUse"]
                if tu["name"] == "search_documents":
                    hits = search_documents(
                        tu["input"]["query"], knowledge_base_id)
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tu["toolUseId"],
                            "content": [{"json": {"results": hits}}]
                        }
                    })

        # -- send tool results back --
        messages.append({"role": "user", "content": tool_results})
        final = brt.converse(
            modelId=MODEL, messages=messages, toolConfig=TOOL_CONFIG)

        print(f"FINAL: {json.dumps(final)}")
        print(f"CONTENT: {final['output']['message']['content'][0]['text']}")

        # final["output"]["message"]["content"][0]["text"], hits
        return final['output']['message']['content'][0]['text']

    print(f"OUT: {out}")
    print(f"CONTENT: {out["content"][0]["text"]}")

    # model answered without needing the tool
    return out["content"][0]["text"]


def load_history(session_id, n=10):

    print(f"SESSION_ID: {session_id}")

    r = ddb.query(TableName="clarvo-conversations",
                  KeyConditionExpression="session_id = :s",
                  ExpressionAttributeValues={":s": {"S": session_id}})
    print(f"R: {r}")

    return [{"role": i["role"]["S"], "content": [{"text": i["text"]["S"]}]} for i in reversed(r["Items"])]


def save_turn(session_id, role, text):

    print(f"SAVE_TURN: {text}")
    ddb.put_item(TableName="clarvo-conversations",
                 Item={"session_id": {"S": session_id}, "ts": {"N": str(time.time_ns())}, "role": {"S": role}, "text": {"S": text}})


def lambda_handler(event, context):

    question = event["detail"]["text"]
    session_id = event["detail"]["session_id"]

    history = load_history(session_id)

    print(f"HISTORIES: {history}")

    messages = history + [{"role": "user", "content": [{"text": question}]}]

    print(f"MESSAGES: {messages}")

    answer = ask(messages, event["detail"]["kb_id"])

    print(f"RESPONSE: {json.dumps(answer)}")

    save_turn(session_id, "user", question)
    save_turn(session_id, "user", answer)

    return answer
