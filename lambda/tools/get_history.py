"""
Torvi — getHistory Lambda Tool
Called by Bedrock Agent to fetch payment history for a flat.
Returns last 6 months of payment records from DynamoDB.
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Key

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
dynamodb   = boto3.resource("dynamodb", region_name=AWS_REGION)
table      = dynamodb.Table("torvi-ledger")


def lambda_handler(event, context):
    print(f"📥 getHistory event: {json.dumps(event)}")

    flat_no = None
    months  = 6
    params  = event.get("parameters", [])
    for p in params:
        if p.get("name") == "flat_no":
            flat_no = str(p.get("value", "")).strip().upper()
        if p.get("name") == "months":
            try:
                months = int(p.get("value", 6))
            except:
                months = 6

    if not flat_no:
        return response_body("error", "flat_no parameter is required")

    try:
        result = table.query(
            KeyConditionExpression=Key("flat_no").eq(flat_no),
            ScanIndexForward=False,
            Limit=months
        )
        items = result.get("Items", [])

        if not items:
            return response_body("not_found", f"No history found for Flat {flat_no}")

        history = []
        for item in items:
            history.append({
                "month":           item.get("month"),
                "balance_pending": float(item.get("balance_pending", 0)),
                "amount_received": float(item.get("amount_received", 0)),
                "status":          item.get("status", "Unknown"),
            })

        data = {"flat_no": flat_no, "history": history}
        print(f"✅ getHistory result: {len(history)} months")
        return response_body("success", json.dumps(data))

    except Exception as e:
        print(f"❌ getHistory error: {e}")
        return response_body("error", f"Failed to fetch history: {str(e)}")


def response_body(status: str, text: str) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": "DuesActions",
            "function":    "getHistory",
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": text}
                }
            }
        }
    }
