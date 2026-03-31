import json
import os
import hashlib
import hmac
import time
import urllib.request
import urllib.error
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

# ── Configuration ────────────────────────────────────────────────
WA_TOKEN        = os.environ["WA_TOKEN"]
WA_PHONE_ID     = os.environ["WA_PHONE_ID"]
WA_VERIFY_TOKEN = os.environ["WA_VERIFY_TOKEN"]
WA_APP_SECRET   = os.environ.get("WA_APP_SECRET", "")
AGENT_ID        = os.environ["AGENT_ID"]
AGENT_ALIAS_ID  = os.environ.get("AGENT_ALIAS_ID", "TSTALIASID")
AWS_REGION      = os.environ.get("AWS_REGION", "ap-south-1")
SOCIETY_ID      = os.environ.get("SOCIETY_ID", "SBNP001")
SOCIETY_NAME    = os.environ.get("SOCIETY_NAME", "Siva Balaji Nilayam")

# ── AWS clients ──────────────────────────────────────────────────
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
dynamodb      = boto3.resource("dynamodb", region_name=AWS_REGION)
dedup_table   = dynamodb.Table("torvi-message-dedup")
phone_table   = dynamodb.Table("torvi-phone-mapping")


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "GET":
        return handle_verification(event)
    if method == "POST":
        return handle_message(event)
    return {"statusCode": 405, "body": "Method not allowed"}


# ── Webhook verification ─────────────────────────────────────────
def handle_verification(event):
    params    = event.get("queryStringParameters") or {}
    mode      = params.get("hub.mode", "")
    token     = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token == WA_VERIFY_TOKEN:
        print("✅ Webhook verified")
        return {"statusCode": 200, "body": challenge}
    return {"statusCode": 403, "body": "Forbidden"}


# ── Message handling ─────────────────────────────────────────────
def handle_message(event):
    body_str  = event.get("body", "")
    signature = event.get("headers", {}).get("x-hub-signature-256", "")

    if not verify_signature(body_str, signature):
        print("❌ Invalid signature")
        return {"statusCode": 403, "body": "Invalid signature"}

    try:
        body = json.loads(body_str)
    except Exception:
        return {"statusCode": 400, "body": "Invalid JSON"}

    try:
        change  = body["entry"][0]["changes"][0]["value"]
        if "statuses" in change:
            return {"statusCode": 200, "body": "ok"}
        message = change["messages"][0]
        msg_id  = message["id"]
        phone   = message["from"]
        text    = message.get("text", {}).get("body", "").strip()
        if not text:
            return {"statusCode": 200, "body": "ok"}
    except (KeyError, IndexError) as e:
        print(f"⚠️ Parse error: {e}")
        return {"statusCode": 200, "body": "ok"}

    # Deduplicate
    if is_duplicate(msg_id):
        print(f"⚠️ Duplicate {msg_id}, skipping")
        return {"statusCode": 200, "body": "ok"}

    print(f"📩 Message from {phone}: {text[:80]}")

    # Lookup flat from phone
    flat_no, role = lookup_phone(phone)

    # Enrich message with context
    if flat_no:
        enriched = f"[Society: {SOCIETY_NAME}, Phone: {phone}, Flat: {flat_no}, Role: {role}] {text}"
    else:
        enriched = f"[Society: {SOCIETY_NAME}, Phone: {phone}, Flat: UNKNOWN] {text}"

    # Call Bedrock Agent
    reply = call_bedrock_agent(phone, enriched)
    print(f"🤖 Reply: {reply[:80]}...")

    # Send WhatsApp reply
    send_whatsapp_message(phone, reply)

    return {"statusCode": 200, "body": "ok"}


# ── Phone → Flat lookup ──────────────────────────────────────────
def lookup_phone(phone: str):
    try:
        resp = phone_table.get_item(Key={"phone": phone})
        item = resp.get("Item")
        if item:
            return item.get("flat_no"), item.get("role", "resident")
    except Exception as e:
        print(f"⚠️ Phone lookup error: {e}")
    return None, None


# ── Deduplication ────────────────────────────────────────────────
def is_duplicate(msg_id: str) -> bool:
    try:
        dedup_table.put_item(
            Item={"message_id": msg_id, "ttl": int(time.time()) + 86400},
            ConditionExpression="attribute_not_exists(message_id)"
        )
        return False
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return True
        print(f"⚠️ Dedup error: {e}")
        return False


# ── Bedrock Agent ────────────────────────────────────────────────
def call_bedrock_agent(phone: str, text: str) -> str:
    now        = datetime.utcnow()
    session_id = f"{phone}:{now.year}-{now.month:02d}"

    NON_RETRYABLE = {"ResourceNotFoundException", "AccessDeniedException", "ValidationException"}
    RETRYABLE     = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"}

    for attempt in range(3):
        try:
            response = bedrock_agent.invoke_agent(
                agentId=AGENT_ID,
                agentAliasId=AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=text
            )
            reply = ""
            for event in response["completion"]:
                if "chunk" in event:
                    reply += event["chunk"]["bytes"].decode("utf-8")
            return reply.strip() or "Sorry, I couldn't process that. Please try again."

        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in NON_RETRYABLE:
                print(f"🚨 Non-retryable Bedrock error: {code}")
                return "Torvi is temporarily unavailable. Please try again later."
            elif code in RETRYABLE:
                wait = 2 ** attempt
                print(f"⚠️ Bedrock {code} attempt {attempt+1}. Retrying in {wait}s...")
                if attempt < 2:
                    time.sleep(wait)
            else:
                print(f"⚠️ Bedrock error {code}: {e}")
                if attempt < 2:
                    time.sleep(2)

        except Exception as e:
            print(f"⚠️ Bedrock attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return "I'm having trouble right now 🙏 Please send your message again in a moment."


# ── WhatsApp send ────────────────────────────────────────────────
def send_whatsapp_message(to: str, text: str) -> bool:
    url     = f"https://graph.facebook.com/v22.0/{WA_PHONE_ID}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to, "type": "text",
        "text": {"body": text}
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }

    NON_RETRYABLE = {401, 403, 400}
    RETRYABLE     = {429, 500, 502, 503, 504}

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                print(f"✅ WhatsApp sent: {result.get('messages',[{}])[0].get('id','?')}")
                return True

        except urllib.error.HTTPError as e:
            if e.code in NON_RETRYABLE:
                if e.code == 401:
                    print("🚨 WA_TOKEN expired — update Lambda env var")
                elif e.code == 403:
                    print(f"🚨 {to} not whitelisted or permission denied")
                return False
            elif e.code in RETRYABLE:
                wait = 2 ** attempt
                print(f"⚠️ WhatsApp {e.code} attempt {attempt+1}. Retry in {wait}s...")
                if attempt < 2:
                    time.sleep(wait)
            else:
                print(f"⚠️ WhatsApp HTTP {e.code}")
                if attempt < 2:
                    time.sleep(2)

        except Exception as e:
            print(f"⚠️ WhatsApp attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    print(f"🚨 CRITICAL: All retries failed for {to}")
    return False


# ── Signature verification ───────────────────────────────────────
def verify_signature(body: str, signature: str) -> bool:
    if not WA_APP_SECRET:
        return True
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        WA_APP_SECRET.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
