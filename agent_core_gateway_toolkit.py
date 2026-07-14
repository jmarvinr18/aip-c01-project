import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

gwc = GatewayClient(region_name="ap-southeast-1")

# Creates a Gateway + Cognito JWT inbound authorizer (least code)
gateway = gwc.create_mcp_gateway(name="clarvo-tools-gw")

# Target B: the ACT Lambda (explicit tool schema)
gwc.create_mcp_gateway_target(
    gateway=gateway, name="clarvoDraftReminder", target_type="lambda",
    target_payload={
        "lambdaArn": "arn:aws:lambda:ap-southeast-1:408897322877:function:clarvoDraftReminder",
        "toolSchema": {"inlinePayload": [{
            "name": "draft_reminder",
            "description": "Draft a renewal reminder email given a renewal_date (ISO) and client_name.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "renewal_date": {"type": "string", "description": "ISO date e.g. 2026-09-01"},
                    "client_name":  {"type": "string"},
                    "days_before":  {"type": "integer", "description": "lead time in days"}
                },
                "required": ["renewal_date"]
            }
        }]}
    },
    credentials=None  # defaults to GATEWAY_IAM_ROLE
)
