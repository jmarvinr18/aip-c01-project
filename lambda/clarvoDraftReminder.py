import json, datetime

def lambda_handler(event, context):
    # Gateway passes inputSchema properties directly as the event
    delimiter = "___"
    raw = context.client_context.custom["bedrockAgentCoreToolName"]
    tool = raw[raw.index(delimiter) + len(delimiter):] if delimiter in raw else raw

    if tool == "draft_reminder":
        renewal_date = event["renewal_date"]        # e.g. "2026-09-01"
        client_name  = event.get("client_name", "the client")
        days_before  = int(event.get("days_before", 30))
        rd = datetime.date.fromisoformat(renewal_date)
        remind_on = rd - datetime.timedelta(days=days_before)
        draft = (
            f"Subject: Upcoming renewal for {client_name} on {renewal_date}\n\n"
            f"Reminder scheduled for {remind_on.isoformat()} "
            f"({days_before} days prior). Please confirm renewal terms."
        )
        return {"draft": draft, "remind_on": remind_on.isoformat()}

    return {"error": f"unknown tool {tool}"}