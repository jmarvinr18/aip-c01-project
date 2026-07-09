import json
import boto3

ddb = boto3.client("dynamodb", region_name="ap-southeast-1")


def lambda_handler(session_id: str, n: int):

    response = ddb.query(TableName="clarvo-conversations",
                         KeyConditionExpression="session_id = :s",
                         ExpressionAttributeValues={":s": {"S": session_id}},
                         ScanIndexForward=False, Limit=n)
    return response
