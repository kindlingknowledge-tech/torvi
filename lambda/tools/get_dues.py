"""
Torvi — getDues Lambda Tool
Called by Bedrock Agent to fetch current dues for a flat.
Returns latest month balance from DynamoDB.
"""
import json
import os
import boto3
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
dynamodb   = boto3.resource("dynamodb", region_name=AWS_REGION)
table      = dynamodb.Table("torvi-ledger")


def lambda_handler(event, context):
    print(f"📥 getDues event: {json.dumps(event)}")

    # Extract flat_no from agent parameters
    flat_no = None
    params  = event.get("parameters", [])
    for p in params:
        if p.get("name") == "flat_no":
            flat_no = str(p.get("value", "")).strip().upper()
            break

    if not flat_no:
        return response_body("error", "flat_no parameter is required")

    try:
        # Query all months for this flat, sorted by month descending
        result = table.query(
            KeyConditionExpression=Key("flat_no").eq(flat_no),
            ScanIndexForward=False,  # descending — latest first
            Limit=3  # get last 3 months
        )
        items = result.get("Items", [])

        if not items:
            return response_body("not_found", f"No records found for Flat {flat_no}")

        latest = items[0]
        month  = latest.get("month", "")
        balance = float(latest.get("balance_pending", 0))
        status  = latest.get("status", "Unknown")
        amount_received = float(latest.get("amount_received", 0))
        total_expenses  = float(latest.get("total_expenses", 0))

        # Expense breakdown
        breakdown = {
            "manjeera_bill":    float(latest.get("manjeera_bill", 0)),
            "watchman_salary":  float(latest.get("watchman_salary", 0)),
            "trash":            float(latest.get("trash", 0)),
            "electricity_bill": float(latest.get("electricity_bill", 0)),
            "diesel":           float(latest.get("diesel", 0)),
            "lift_maintenance": float(latest.get("lift_maintenance", 0)),
            "others":           float(latest.get("others", 0)),
        }

        data = {
            "flat_no":         flat_no,
            "month":           month,
            "balance_pending": balance,
            "status":          status,
            "amount_received": amount_received,
            "total_expenses":  total_expenses,
            "breakdown":       breakdown
        }

        print(f"✅ getDues result: {json.dumps(data)}")
        return response_body("success", json.dumps(data))

    except Exception as e:
        print(f"❌ getDues error: {e}")
        return response_body("error", f"Failed to fetch dues: {str(e)}")


def response_body(status: str, text: str) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": "DuesActions",
            "function":    "getDues",
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": text}
                }
            }
        }
    }
