# Torvi 🏠

> **A society that runs itself.**
> WhatsApp-first AI assistant for Indian housing society management.

[![Status](https://img.shields.io/badge/Phase-1-blue)](https://torvi.in)
[![Stack](https://img.shields.io/badge/Stack-AWS%20Bedrock%20%2B%20WhatsApp-orange)](https://torvi.in)
[![Region](https://img.shields.io/badge/Region-ap--south--1-green)](https://torvi.in)

---

## What is Torvi?

Residents type on WhatsApp. Torvi answers instantly.

```
Resident: "What are my dues?"
Torvi:    "March dues: ₹2,500 pending (Flat 301)"

Resident: "mera paisa gaya?"
Torvi:    "✅ ₹2,500 received on 14 Mar 2026"
```

No app download. No login. Phone number = identity.

---

## Architecture

```
Resident (WhatsApp)
        │
        ▼
WhatsApp Cloud API (Meta)
        │ webhook POST
        ▼
Lambda Function URL → Webhook Lambda (<500ms → returns 200)
        │
        ▼
Amazon Bedrock Agent (Claude Haiku 4.5)
        │
        ├── getDues Lambda    → DynamoDB torvi-ledger
        ├── getHistory Lambda → DynamoDB torvi-ledger
        └── KB (vendor, FAQ)  → Pinecone
        │
        ▼
WhatsApp reply sent
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Messaging | WhatsApp Cloud API (Meta) |
| AI Agent | Amazon Bedrock — Claude Haiku 4.5 |
| Compute | AWS Lambda (Python 3.12) |
| Data | Amazon DynamoDB |
| Knowledge Base | Amazon Bedrock KB + Pinecone |
| Region | ap-south-1 (Mumbai) |

---

## Repository Structure

```
torvi/
├── lambda/
│   ├── webhook/          # WhatsApp webhook handler
│   │   └── lambda_handler.py
│   ├── migration/        # One-time data migration
│   │   └── lambda_handler.py
│   └── tools/            # Bedrock Agent tools
│       ├── get_dues.py
│       └── get_history.py
├── data/
│   ├── migration/        # Migration scripts
│   └── samples/          # Anonymised sample data
├── prompts/              # System prompts (versioned)
│   └── system_prompt_v1.txt
├── docs/                 # Architecture & design docs
├── web/                  # torvi.in landing page
│   └── index.html
└── tests/                # Unit tests
```

---

## Environment Variables (Lambda)

```bash
WA_TOKEN        = "your-permanent-meta-token"
WA_PHONE_ID     = "1043711018824704"
WA_VERIFY_TOKEN = "torvi_poc_2026"
WA_APP_SECRET   = "your-app-secret"
AGENT_ID        = "Q8EFRSD64T"
AGENT_ALIAS_ID  = "TSTALIASID"
SOCIETY_ID      = "SBNP001"
SOCIETY_NAME    = "Siva Balaji Nilayam"
```

---

## DynamoDB Tables

| Table | PK | SK | Purpose |
|-------|----|----|---------|
| `torvi-phone-mapping` | `phone` | — | Phone → flat lookup |
| `torvi-ledger` | `flat_no` | `month` | Dues & payment history |
| `torvi-message-dedup` | `message_id` | — | Duplicate prevention |

---

## Quick Start

### 1. Run migration (one-time)
Invoke `torvi-migration` Lambda manually from AWS Console.

### 2. Test agent
Go to Bedrock → Agents → Test with:
```
[Society: Siva Balaji Nilayam, Phone: 919849233398, Flat: 101, Role: admin] What are my dues?
```

### 3. Test WhatsApp
Send "Hi" to the Meta test number from a whitelisted phone.

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | KB-based PoC, WhatsApp loop proven |
| Phase 1 | 🔄 Current | DynamoDB + Lambda tools, real-time dues |
| Phase 2 | ⏳ Planned | Payments (Razorpay/PhonePe), receipts |
| Phase 3 | ⏳ Planned | Admin web portal, multi-society |

---

## Contact

**Torvi Technologies**
📧 hellotorvi@gmail.com
🌐 [torvi.in](https://torvi.in)
📍 Hyderabad, India

*Built with ❤️ for Indian housing societies*
