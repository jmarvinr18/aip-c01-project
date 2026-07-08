import boto3, json, os
brt = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
ddb = boto3.client("dynamodb")
ANSWER_MODEL = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"

def load_history(sid, n=10):
    r = ddb.query(TableName="clarvo-conversations",
        KeyConditionExpression="session_id=:s",
        ExpressionAttributeValues={":s":{"S":sid}}, ScanIndexForward=False, Limit=n)
    return [{"role":i["role"]["S"],"content":[{"text":i["text"]["S"]}]} for i in reversed(r["Items"])]

def lambda_handler(event, _):
    rc = event["requestContext"]
    conn_id, domain, stage = rc["connectionId"], rc["domainName"], rc["stage"]
    apigw = boto3.client("apigatewaymanagementapi",
                         endpoint_url=f"https://{domain}/{stage}")   # NOTE: https, not wss

    body = json.loads(event.get("body") or "{}")
    question = body.get("question", "")
    sid = body.get("session_id", "anon")

    messages = load_history(sid) + [{"role":"user","content":[{"text":question}]}]

    full = ""
    resp = brt.converse_stream(modelId=ANSWER_MODEL, messages=messages,
                               inferenceConfig={"maxTokens":800,"temperature":0.3})
    for ev in resp["stream"]:
        if "contentBlockDelta" in ev:
            tok = ev["contentBlockDelta"]["delta"].get("text","")
            if tok:
                full += tok
                apigw.post_to_connection(ConnectionId=conn_id, Data=tok.encode())   # push token
    apigw.post_to_connection(ConnectionId=conn_id,
                             Data=json.dumps({"done":True}).encode())               # end signal

    # persist the turn
    import time
    for role,text in (("user",question),("assistant",full)):
        ddb.put_item(TableName="clarvo-conversations", Item={
            "session_id":{"S":sid},"ts":{"N":str(time.time_ns())},
            "role":{"S":role},"text":{"S":text}})
    return {"statusCode":200}