"""
Torvi — One-time migration Lambda
Reads CSVs from S3 and writes to DynamoDB tables.
Trigger: Manual invoke only.
"""
import json
import os
import csv
import boto3
from io import StringIO
from decimal import Decimal

S3_BUCKET    = os.environ.get("S3_BUCKET", "torvi-knowledge-base-data")
S3_PREFIX    = os.environ.get("S3_PREFIX", "siva_balaji_nilayam_nizampet/")
AWS_REGION   = os.environ.get("AWS_REGION", "ap-south-1")
SOCIETY_ID   = os.environ.get("SOCIETY_ID", "SBNP001")

s3       = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

ledger_table = dynamodb.Table("torvi-ledger")
phone_table  = dynamodb.Table("torvi-phone-mapping")


def lambda_handler(event, context):
    print("🚀 Torvi migration starting...")
    results = {}

    # Migrate phone mapping
    try:
        phone_count = migrate_phone_mapping()
        results["phone_mapping"] = {"status": "success", "count": phone_count}
        print(f"✅ Phone mapping: {phone_count} records migrated")
    except Exception as e:
        results["phone_mapping"] = {"status": "error", "error": str(e)}
        print(f"❌ Phone mapping failed: {e}")

    # Migrate ledger
    try:
        ledger_count = migrate_ledger()
        results["ledger"] = {"status": "success", "count": ledger_count}
        print(f"✅ Ledger: {ledger_count} records migrated")
    except Exception as e:
        results["ledger"] = {"status": "error", "error": str(e)}
        print(f"❌ Ledger failed: {e}")

    print(f"🏁 Migration complete: {json.dumps(results)}")
    return {"statusCode": 200, "body": json.dumps(results)}


def read_csv_from_s3(filename: str) -> list:
    key  = S3_PREFIX + filename
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    body = resp["Body"].read().decode("utf-8")
    reader = csv.DictReader(StringIO(body))
    return list(reader)


def migrate_phone_mapping() -> int:
    rows  = read_csv_from_s3("phone_mapping.csv")
    count = 0
    with phone_table.batch_writer() as batch:
        for row in rows:
            phone = str(row.get("phone", "")).strip()
            if not phone:
                continue
            batch.put_item(Item={
                "phone":      phone,
                "flat_no":    str(row.get("flat_no", "")).strip(),
                "role":       str(row.get("role", "resident")).strip(),
                "status":     str(row.get("status", "active")).strip(),
                "society_id": SOCIETY_ID
            })
            count += 1
    return count


def migrate_ledger() -> int:
    rows  = read_csv_from_s3("monthly_ledger.csv")
    count = 0
    with ledger_table.batch_writer() as batch:
        for row in rows:
            flat_no = str(row.get("flat_no", "")).strip()
            month   = str(row.get("month", "")).strip()
            if not flat_no or not month:
                continue

            def to_decimal(val):
                try:
                    return Decimal(str(val)).quantize(Decimal("0.01"))
                except:
                    return Decimal("0")

            batch.put_item(Item={
                "flat_no":         flat_no,
                "month":           month,
                "society_id":      SOCIETY_ID,
                "opening_balance": to_decimal(row.get("opening_balance", 0)),
                "amount_received": to_decimal(row.get("amount_received", 0)),
                "total_expenses":  to_decimal(row.get("total_expenses", 0)),
                "balance_pending": to_decimal(row.get("balance_pending", 0)),
                "status":          str(row.get("status", "Pending")).strip(),
                "manjeera_bill":   to_decimal(row.get("manjeera_bill", 0)),
                "watchman_salary": to_decimal(row.get("watchman_salary", 0)),
                "trash":           to_decimal(row.get("trash", 0)),
                "electricity_bill":to_decimal(row.get("electricity_bill", 0)),
                "diesel":          to_decimal(row.get("diesel", 0)),
                "lift_maintenance":to_decimal(row.get("lift_maintenance", 0)),
                "others":          to_decimal(row.get("others", 0)),
            })
            count += 1
    return count
