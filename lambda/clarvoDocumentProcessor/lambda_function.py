import json
import boto3
import os
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path

s3 = boto3.client("s3", region_name="ap-southeast-1")
textract = boto3.client("textract", region_name="ap-southeast-1")
comprehend = boto3.client("comprehend", region_name="ap-southeast-1")


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

    file_path = Path(key)

    extension = file_path.suffix
    clean_ext = extension.lstrip(".")  # Returns 'pdf'

    print(f"File Path: {file_path}")
    print(f"Extension: {clean_ext}")

    # textract = event.get("textract", {})
    # job_id = textract.get("JobId")

    print(f"THIS IS KEY: {key}")

    print(f"THIS TEXTRACT: {textract}")

    job_id = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )["JobId"]

    documentStatus = "IN_PROGRESS"

    while documentStatus == "IN_PROGRESS":
        response = textract.get_document_text_detection(JobId=job_id)
        documentStatus = response["JobStatus"]

    print(f"DOCUMENT STATUS: {documentStatus}")
    print(f"THIS TEXTRACT OBJECT ID: {job_id}")

    if "textract" in event:

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
        print(f'REKOGNITION EVENT: {event["rekognition"]}')
        labels = event["rekognition"]["Labels"]
        text = ", ".join(
            f'{lbl["Name"]} ({round(lbl["Confidence"])}%)' for lbl in labels)

    else:
        text = ""

    # stay under Comprehend's 100KB/call cap (chunk later in lab 1.12)
    text = text[:90000]

    entities = comprehend.detect_entities(Text=text, LanguageCode="en")[
        "Entities"] if text else []
    pii = comprehend.detect_pii_entities(Text=text, LanguageCode="en")[
        "Entities"] if text else []

    record = {
        "source_key": key,
        "text": text,
        "entities": [{"type": e["Type"], "text": e["Text"], "score": e["Score"]} for e in entities],
        "pii_spans": [{"type": p["Type"], "begin": p["BeginOffset"], "end": p["EndOffset"]} for p in pii],
        "char_count": len(text),
    }

    metaData = {
        "metadataAttributes": {
            "ingested_at": event["time"],
            "source": key,
            "doc_type": clean_ext
        }
    }
    # THIS IS AN UPDATEEEEEEE
    print(f"EVENT: {json.dumps(event)}")
    print(f"CONTEXT: {context}")
    print(f"RECORD: {record}")
    print(f"METADATA: {metaData}")

    out_key = "processed/" + \
        os.path.splitext(os.path.basename(key))[0] + ".jsonl"

    s3.put_object(Bucket=bucket, Key=out_key,
                  Body=(json.dumps(record) + "\n").encode("utf-8"),
                  ServerSideEncryption="aws:kms")

    kb_source_key = f"kb-source/{os.path.splitext(os.path.basename(key))[0]}.txt.metadata.json"
    s3.put_object(Bucket=bucket, Key=kb_source_key,
                  Body=(json.dumps(metaData) + "\n").encode("utf-8"),
                  ServerSideEncryption="aws:kms")

    kb_source_text_key = f"kb-source/{os.path.splitext(os.path.basename(key))[0]}.txt"

    print(f"TEXT: {text}")

    s3.put_object(Bucket=bucket, Key=kb_source_text_key,
                  Body=(text).encode("utf-8"),
                  ServerSideEncryption="aws:kms")

    return {"processed_key": out_key, "char_count": len(text)}
