import json, boto3, os, urllib.parse
from urllib.parse import urlparse

s3 = boto3.client("s3")
textract = boto3.client("textract")
comprehend = boto3.client("comprehend")


def gather_textract_text(job_id):
    text, token = [], None

    while True:
        kw = {"JobId": job_id, **({"NextToken": token} if token else {})}
        resp = textract.get_document_text_detection(**kw)

        print(f"THIS TEXTRACT RESPONSE: {resp}")

        for b in resp["Blocks"]:
            if b["BlockType"] == "LINE":
                text.append(b["Text"])

        token = resp.get("NextToken")

        if not token:
            break
    print(f"TEXT: {text}")
    return "\n".join(text)

def parse_s3_uri(uri):
    """Handle s3://, path-style, and virtual-hosted-style HTTPS URIs."""
    p = urlparse(uri)
    if p.scheme == "s3":
        return p.netloc, p.path.lstrip("/")
    host, path = p.netloc, p.path.lstrip("/")
    # virtual-hosted: <bucket>.s3[.region].amazonaws.com/<key>
    if ".s3" in host and not host.startswith("s3"):
        bucket = host.split(".s3")[0]
        return bucket, path
    # path-style: s3[.region].amazonaws.com/<bucket>/<key>
    parts = path.split("/", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def lambda_handler(event, context):

    bucket = event["detail"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event["detail"]["object"]["key"])

    textract = event.get("textract", {})
    job_id = textract.get("JobId")

    print(f"THIS IS KEY: ${key}")

    if "textract" in event:
        print(f"THIS TEXTRACT OBJECT: {job_id}")
        text = gather_textract_text(job_id)

    elif "transcribe" in event:
        uri = event["transcribeResult"]["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        # tb, tk = uri.split("/", 3)[2], uri.split("/", 3)[3]
        tb, tk = parse_s3_uri(uri)

        print(f"URI: {uri}")
        print(f"TB: {tb}")
        print(f"TK: {tk}")

        body = json.loads(s3.get_object(Bucket=tb, Key=tk)["Body"].read())
        text = body["results"]["transcripts"][0]["transcript"]
    elif "rekognition" in event:
        print(f"REKOGNITION EVENT: {event["rekognition"]}")
        labels = event["rekognition"]["Labels"]
        text = ", ".join(f'{lbl["Name"]} ({round(lbl["Confidence"])}%)' for lbl in labels)

    else:
        text = ""

    text = text[:90000]  # stay under Comprehend's 100KB/call cap (chunk later in lab 1.12)

    entities = comprehend.detect_entities(Text=text, LanguageCode="en")["Entities"] if text else []
    pii = comprehend.detect_pii_entities(Text=text, LanguageCode="en")["Entities"] if text else []

    record = {
        "source_key": key,
        "text": text,
        "entities": [{"type": e["Type"], "text": e["Text"], "score": e["Score"]} for e in entities],
        "pii_spans": [{"type": p["Type"], "begin": p["BeginOffset"], "end": p["EndOffset"]} for p in pii],
        "char_count": len(text),
    }


    ### THIS IS AN UPDATEEEEEEE

    print(f"RECORD: {record}")

    out_key = "processed/" + os.path.splitext(os.path.basename(key))[0] + ".jsonl"
    s3.put_object(Bucket=bucket, Key=out_key,
                  Body=(json.dumps(record) + "\n").encode("utf-8"),
                  ServerSideEncryption="aws:kms")
    return {"processed_key": out_key, "char_count": len(text)}
