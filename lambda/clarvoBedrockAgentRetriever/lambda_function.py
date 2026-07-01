import json
import boto3
import os
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path

s3 = boto3.client("s3", region_name="ap-southeast-1")
agent_rt = boto3.client("bedrock-agent-runtime", region_name="ap-southeast-1")
brt = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
MODEL = "apac.anthropic.claude-3-haiku-20240307-v1:0"

TOOL_CONFIG = {
    "tools": [{
        "toolSpec": {
            "name": "search_documents",
            "description": """Search the company's document knowledge base for relevant passages. \
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


def ask(question: str, knowledge_base_id: str, num_results: int = 5):
    messages = [{"role": "user", "content": [{"text": question}]}]

    # -- turn 1: model may request the tool --
    response = brt.converse(
        modelId=MODEL, messages=messages, toolConfig=TOOL_CONFIG)
    out = response["output"]["message"]

    messages.append(out)

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

        print(f"FINAL: {final}")
        print(f"CONTENT: {final["output"]["message"]["content"]}")

        return final["output"]["message"]["content"][0]["text"], hits

    print(f"OUT: {out}")
    print(f"CONTENT: {out["content"]}")

    # model answered without needing the tool
    return out


def lambda_handler(event, context):
    response = ask(event["detail"]["text"], event["detail"]["kb_id"])
    print(f"{response["content"][0]["text"], []}")
    return response
