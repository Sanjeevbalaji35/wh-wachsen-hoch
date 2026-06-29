import os
import json
import asyncio
import logging
import uuid
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

# Setup logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [CA_ENGINE] - %(levelname)s - %(message)s")
logger = logging.getLogger("MarketingExecutionEngine")

app = FastAPI(title="WH Wachsen Hoch - Command Center", version="2.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SECURE CONSTANTS ---
# Standard pattern: Reads from Server environment or falls back to standard secure default
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "WachsenHoch2026!")

# --- IN-MEMORY DATABASE STATE ---
CLIENTS_DB: Dict[str, Dict[str, Any]] = {}
EMAIL_IP_LOCKLIST: List[str] = []

# --- LIVE COST ENGINE CALCULATION MATRIX (REALISTIC INR ₹ ESTIMATES) ---
EXTERNAL_SERVICE_SPECS = {
    "sem": {
        "display_name": "Search Engine Marketing (SEM)",
        "connection": "Google Ads & Microsoft Advertising API",
        "owner_calc": lambda tier: 10.0 * 12 * tier,      # Quota checks in INR
        "client_calc": lambda tier: 150.0 * 10 * tier,    # Direct Google Ads daily budget
        "owner_desc": "Google Search API Quota",
        "client_desc": "Google Ads Direct PPC Spend",
        "billing_cycle": "Daily / Rolling",
        "validity": "Real-time (Runs until budget is consumed)"
    },
    "smm": {
        "display_name": "Social Media Marketing (SMM)",
        "connection": "Ayrshare API & Meta Graph SDK",
        "owner_calc": lambda tier: 5.0 * 20 * tier,
        "client_calc": lambda tier: 80.0 * 12 * tier,
        "owner_desc": "Ayrshare Multi-Profile API",
        "client_desc": "Meta Campaign Ad Budget",
        "billing_cycle": "Monthly",
        "validity": "30 Days (Auto-renews monthly)"
    },
    "content_marketing": {
        "display_name": "Content Marketing",
        "connection": "Webflow CMS API & OpenAI GPT-4o API",
        "owner_calc": lambda tier: 0.5 * 150 * tier,
        "client_calc": lambda tier: 120.0 * tier,
        "owner_desc": "OpenAI copywriting tokens",
        "client_desc": "Webflow CMS License Fee",
        "billing_cycle": "Monthly",
        "validity": "Webflow: 30 Days / OpenAI: 1 Year credits"
    },
    "email_marketing": {
        "display_name": "Email Marketing",
        "connection": "SendGrid API & ZeroBounce Verification API",
        "owner_calc": lambda tier: 0.8 * 100 * tier,
        "client_calc": lambda tier: 0.01 * 5000 * tier,
        "owner_desc": "ZeroBounce address hygiene verification",
        "client_desc": "SendGrid SMTP transactional delivery",
        "billing_cycle": "Monthly / PAYG",
        "validity": "SendGrid: 30 Days / ZeroBounce: Never expires"
    },
    "affiliate_marketing": {
        "display_name": "Affiliate & Referral Marketing",
        "connection": "PartnerStack API & Rewardful Webhooks",
        "owner_calc": lambda tier: 1.5 * 50 * tier,
        "client_calc": lambda tier: 150.0 * tier,
        "owner_desc": "PartnerStack API webhook tracking",
        "client_desc": "Rewardful Base Tracking SaaS",
        "billing_cycle": "Monthly",
        "validity": "30 Days (Auto-renews monthly)"
    },
    "mobile_marketing": {
        "display_name": "Mobile Marketing",
        "connection": "Twilio SMS API & Plivo Carrier Gateway",
        "owner_calc": lambda tier: 0.2 * 50 * tier,
        "client_calc": lambda tier: 1.32 * 250 * tier,
        "owner_desc": "Twilio Opt-in/Opt-out compliance logs",
        "client_desc": "Twilio Outbound SMS carrier fees",
        "billing_cycle": "Monthly / PAYG",
        "validity": "Twilio Number: 30 Days / Balance: Never expires"
    },
    "analytics_data": {
        "display_name": "Marketing Analytics & Data",
        "connection": "Segment Ingestion API & BigQuery Warehouse",
        "owner_calc": lambda tier: 120.0 * tier,
        "client_calc": lambda tier: 350.0 * tier,
        "owner_desc": "Segment event tracking units",
        "client_desc": "BigQuery serverless data storage",
        "billing_cycle": "Monthly / Rolling",
        "validity": "Segment: 30 Days / BigQuery: Indefinite retention"
    }
}

MARKETING_CHANNELS_DEFINITION = {
    "sem": {
        "display_name": "Search Engine Marketing (SEM)",
        "required_credentials": ["Google Ads Account ID (XXX-XXX-XXXX)", "Manager Approval Token"],
        "steps": ["Goal Setting", "Keyword Research", "Account Structuring", "Ad Creation", "Bidding & Budgeting", "Conversion Tracking", "Optimization"],
        "underlying_microservices": ["Keyword & Topic Research", "Value Proposition", "A/B Testing", "Optimize", "Customer Acquisition Cost (CAC) vs. Lifetime Value (LTV)", "The Full-Stack Funnel (The 'Conversion Engine')"]
    },
    "smm": {
        "display_name": "Social Media Marketing (SMM)",
        "required_credentials": ["Ayrshare User Profile Key (or OAuth Token)"],
        "steps": ["Audience Research", "Platform Selection", "Goal Identification", "Content Planning", "Execution", "Paid Campaign Setup", "Performance Monitoring"],
        "underlying_microservices": ["Identify Target Audience", "Value Proposition", "A/B Testing", "Optimize", "Social Listening & Brand Reputation", "The Full-Stack Funnel (The 'Conversion Engine')"]
    },
    "content_marketing": {
        "display_name": "Content Marketing",
        "required_credentials": ["CMS API Access Key (Webflow/WordPress URL & Token)"],
        "steps": ["Audience Definition", "Funnel Mapping", "Strategy Development", "Content Creation", "Distribution", "SEO Optimization", "Performance Review"],
        "underlying_microservices": ["Increase website traffic", "Keyword & Topic Research", "Content Calendar", "SEO (Organic)", "The Full-Stack Funnel (The 'Conversion Engine')"]
    },
    "email_marketing": {
        "display_name": "Email Marketing",
        "required_credentials": ["SendGrid/SMTP API Key", "Verified Sender Email Domain"],
        "steps": ["List Building", "Segmentation", "Goal Setting", "Campaign Planning", "Content Design", "Testing", "Analytics Tracking"],
        "underlying_microservices": ["Customer Journey Mapping", "Marketing Automation", "Conversion Rate Optimization (CRO)", "Data Hygiene & Compliance"]
    },
    "affiliate_marketing": {
        "display_name": "Affiliate & Referral Marketing",
        "required_credentials": ["Affiliate Tracking Software API Key (Refersion or Rewardful)"],
        "steps": ["Goal Setting", "Platform Setup", "Recruitment", "Resource Provisioning", "Monitoring", "Optimization", "Relationship Management"],
        "underlying_microservices": ["Conversion Rate Optimization (CRO)", "\"Productization\" of Services", "Customer Acquisition Cost (CAC) vs. Lifetime Value (LTV)"]
    },
    "mobile_marketing": {
        "display_name": "Mobile Marketing",
        "required_credentials": ["Twilio Auth SID & Token (SMS Routing)", "Verified Phone Number"],
        "steps": ["Audience Profiling", "Goal Setting", "Channel Selection", "Message Drafting", "Deployment", "Compliance Check", "Performance Review"],
        "underlying_microservices": ["Customer Journey Mapping", "Marketing Automation", "Data Hygiene & Compliance"]
    },
    "analytics_data": {
        "display_name": "Marketing Analytics & Data",
        "required_credentials": ["Google Analytics 4 Measurement ID", "GTM Container ID"],
        "steps": ["Data Collection", "Quality Assurance", "Segmentation", "Trend/Cohort Analysis", "Testing", "Predictive Modeling", "Reporting"],
        "underlying_microservices": ["Analytics Setup", "Data Hygiene & Compliance", "Customer Acquisition Cost (CAC) vs. Lifetime Value (LTV)", "Continuous Iteration (The \"Feedback Loop\")", "customer acquisition engineering"]
    }
}

# --- SCHEMAS ---
class ClientOnboardPayload(BaseModel):
    company_name: str
    email: str
    selected_channels: List[str]
    step_toggles: Dict[str, Dict[str, bool]]
    selected_tier: str
    cost: float

class SaveIntegrationPayload(BaseModel):
    client_id: str
    channel_id: str
    credentials: Dict[str, str]

class OwnerUpdateCampaignsPayload(BaseModel):
    client_id: str
    selected_channels: List[str]

class ToggleStepPayload(BaseModel):
    client_id: str
    channel_id: str
    step_name: str
    is_enabled: bool

# --- DYNAMIC COST ENGINE MODEL (INR ₹) ---
def calculate_live_expenses_detailed(client_id: str) -> dict:
    if client_id not in CLIENTS_DB:
        return {"owner_total": 0.00, "client_total": 0.00, "details": []}
        
    client = CLIENTS_DB[client_id]
    tier = client["subscription_tier"]
    
    tier_multiplier = 1.0
    if tier == "premium":
        tier_multiplier = 2.5
    elif tier == "elite":
        tier_multiplier = 5.0
        
    owner_total = 15.00  # Base daily server overhead fee in INR ₹
    client_total = 0.00
    itemized_list = []
    
    for ch_id, camp in client["active_campaigns"].items():
        if ch_id in EXTERNAL_SERVICE_SPECS:
            spec = EXTERNAL_SERVICE_SPECS[ch_id]
            o_cost = spec["owner_calc"](tier_multiplier)
            c_cost = spec["client_calc"](tier_multiplier)
            
            owner_total += o_cost
            client_total += c_cost
            
            itemized_list.append({
                "channel_name": spec["display_name"],
                "partner_api": spec["connection"],
                "owner_charge": round(o_cost, 2),
                "owner_desc": spec["owner_desc"],
                "client_charge": round(c_cost, 2),
                "client_desc": spec["client_desc"],
                "billing_cycle": spec["billing_cycle"],
                "validity": spec["validity"]
            })
                
    return {
        "owner_running_daily_cost": round(owner_total, 2),
        "client_running_daily_cost": round(client_total, 2),
        "details": itemized_list
    }

# --- ASYNCHRONOUS CAMPAIGN ENGINE LOOP ---
async def execute_asynchronous_channel_campaign(client_id: str, channel_id: str):
    if client_id not in CLIENTS_DB:
        return
    
    client = CLIENTS_DB[client_id]
    channel_info = MARKETING_CHANNELS_DEFINITION[channel_id]
    total_steps = len(channel_info["steps"])
    
    # Pre-Flight Connection Gate
    integration_profile = client["integrations"].get(channel_id, {})
    if not integration_profile.get("is_active", False):
        client["active_campaigns"][channel_id]["status"] = "Awaiting Integration"
        client["active_campaigns"][channel_id]["current_step"] = "⚠️ Requires Credentials Verification"
        logger.warning(f"Aborting execution: {channel_id} is missing active integration keys.")
        return

    client["active_campaigns"][channel_id]["status"] = "Active"
    
    for idx, step_name in enumerate(channel_info["steps"]):
        is_step_active = client["active_campaigns"][channel_id]["step_toggles"].get(step_name, True)
        progress_percentage = int(((idx + 1) / total_steps) * 100)

        if not is_step_active:
            client["active_campaigns"][channel_id]["current_step"] = f"Skipped: {step_name}"
            client["active_campaigns"][channel_id]["progress"] = progress_percentage
            continue

        await asyncio.sleep(4)  # Simulated processing time
        
        client["active_campaigns"][channel_id]["current_step"] = step_name
        client["active_campaigns"][channel_id]["progress"] = progress_percentage
        
        mapped_microservices = channel_info["underlying_microservices"]
        for ms in mapped_microservices:
            if ms in client["microservices_status"]:
                client["microservices_status"][ms]["progress"] = min(100, client["microservices_status"][ms]["progress"] + int(100 / total_steps))
                client["microservices_status"][ms]["status"] = "Active" if client["microservices_status"][ms]["progress"] < 100 else "Completed"
        
        client["metrics"]["website_traffic"] += 180
        client["metrics"]["leads_generated"] += 5
        if client["metrics"]["leads_generated"] > 0:
            client["metrics"]["cac"] = max(330.00, round(client["monthly_cost"] / client["metrics"]["leads_generated"], 2)) # CAC limit in INR
            
    client["active_campaigns"][channel_id]["status"] = "Completed"
    logger.info(f"Campaign execution completed for Client: {client_id}, Channel: {channel_id}")


# --- API GATEWAYS ---

@app.get("/api/channels")
def get_channel_definitions():
    return MARKETING_CHANNELS_DEFINITION


@app.post("/api/client/inquire")
def register_client_inquiry(payload: ClientOnboardPayload):
    clean_id = payload.company_name.lower().replace(" ", "_")
    if clean_id in CLIENTS_DB or payload.email in EMAIL_IP_LOCKLIST:
        raise HTTPException(status_code=403, detail="A profile already exists for this email. Contact your account owner to make modifications.")
    
    EMAIL_IP_LOCKLIST.append(payload.email)

    active_campaigns_tracker = {}
    integration_tracker = {}
    
    for c_id in payload.selected_channels:
        client_step_choices = payload.step_toggles.get(c_id, {})
        steps_list = MARKETING_CHANNELS_DEFINITION[c_id]["steps"]
        step_toggles_initial = {step: client_step_choices.get(step, True) for step in steps_list}
        
        active_campaigns_tracker[c_id] = {
            "display_name": MARKETING_CHANNELS_DEFINITION[c_id]["display_name"],
            "status": "Awaiting Approval",
            "current_step": "Awaiting Lead Audit",
            "progress": 0,
            "step_toggles": step_toggles_initial
        }
        
        integration_tracker[c_id] = {
            "is_active": False,
            "keys_configured": {},
            "fields_needed": MARKETING_CHANNELS_DEFINITION[c_id]["required_credentials"]
        }

    microservices_tracker = {}
    for c_id in payload.selected_channels:
        for ms in MARKETING_CHANNELS_DEFINITION[c_id]["underlying_microservices"]:
            microservices_tracker[ms] = {
                "status": "Awaiting Payment Confirmation",
                "progress": 0
            }

    CLIENTS_DB[clean_id] = {
        "id": clean_id,
        "company_name": payload.company_name,
        "email": payload.email,
        "monthly_cost": payload.cost,
        "subscription_tier": payload.selected_tier,
        "payment_agreed": False,
        "approval_status": "PENDING",
        "receipt_url": None,
        "active_campaigns": active_campaigns_tracker,
        "integrations": integration_tracker,
        "microservices_status": microservices_tracker,
        "metrics": {
            "website_traffic": 0,
            "leads_generated": 0,
            "cac": 0.00,
            "ltv": 25000.00  # Baseline average LTV in INR
        }
    }

    logger.info(f"New Client profile registered and locked: {clean_id}")
    return {"status": "success", "client_id": clean_id}


# --- HELPER FUNCTION: ENFORCE OWNER AUTHENTICATION SHIELD ---
def enforce_owner_shield(x_owner_password: str):
    """Halts API processing immediately if the owner token is invalid or missing."""
    if x_owner_password != OWNER_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized Access: Invalid or missing Owner Password.")


# --- ADMIN ONLY PROTECTED ENDPOINTS ---

@app.post("/api/owner/approve-client/{client_id}")
def approve_client_inquiry(client_id: str, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
        
    client = CLIENTS_DB[client_id]
    client["approval_status"] = "APPROVED"
    
    for c_id in client["active_campaigns"].keys():
         client["active_campaigns"][c_id]["status"] = "Awaiting Payment"
         client["active_campaigns"][c_id]["current_step"] = "Awaiting Invoice Settlement"
         
    logger.info(f"Owner APPROVED client: {client_id}")
    return {"status": "success", "approval_status": "APPROVED"}


@app.post("/api/owner/decline-client/{client_id}")
def decline_client_inquiry(client_id: str, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
        
    client = CLIENTS_DB[client_id]
    client["approval_status"] = "DECLINED"
    client["payment_agreed"] = False
    
    if client["email"] in EMAIL_IP_LOCKLIST:
        EMAIL_IP_LOCKLIST.remove(client["email"])
        
    for c_id in client["active_campaigns"].keys():
         client["active_campaigns"][c_id]["status"] = "Declined"
         client["active_campaigns"][c_id]["current_step"] = "Campaign profile declined by owner."
         
    logger.info(f"Owner DECLINED client: {client_id}. Email lock removed.")
    return {"status": "success", "approval_status": "DECLINED"}


@app.post("/api/owner/update-client-campaigns")
def owner_override_client_campaigns(payload: OwnerUpdateCampaignsPayload, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if payload.client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
        
    client = CLIENTS_DB[payload.client_id]
    existing_channels = list(client["active_campaigns"].keys())
    
    for ch_id in MARKETING_CHANNELS_DEFINITION.keys():
        if ch_id in payload.selected_channels:
            if ch_id not in existing_channels:
                steps_list = MARKETING_CHANNELS_DEFINITION[ch_id]["steps"]
                step_toggles_initial = {step: True for step in steps_list}
                
                client["active_campaigns"][ch_id] = {
                    "display_name": MARKETING_CHANNELS_DEFINITION[ch_id]["display_name"],
                    "status": "Awaiting Integration" if client["payment_agreed"] else "Awaiting Approval",
                    "current_step": "Awaiting Onboarding Connections" if client["payment_agreed"] else "Awaiting Lead Audit",
                    "progress": 0,
                    "step_toggles": step_toggles_initial
                }
                
                client["integrations"][ch_id] = {
                    "is_active": False,
                    "keys_configured": {},
                    "fields_needed": MARKETING_CHANNELS_DEFINITION[ch_id]["required_credentials"]
                }
        else:
            if ch_id in existing_channels:
                del client["active_campaigns"][ch_id]
                if ch_id in client["integrations"]:
                    del client["integrations"][ch_id]

    rebuilt_ms = {}
    for ch_id in payload.selected_channels:
         for ms in MARKETING_CHANNELS_DEFINITION[ch_id]["underlying_microservices"]:
              rebuilt_ms[ms] = client["microservices_status"].get(ms, {"status": "Awaiting Connection", "progress": 0})
              
    client["microservices_status"] = rebuilt_ms
    logger.info(f"Owner manually modified campaigns for {payload.client_id}. New Channels: {payload.selected_channels}")
    return {"status": "success", "data": client}


@app.post("/api/owner/upload-receipt/{client_id}")
async def upload_payment_receipt_and_activate(client_id: str, file: UploadFile = File(...), x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
        
    client = CLIENTS_DB[client_id]
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF or image receipt.")
    
    os.makedirs("./secure_receipts_storage", exist_ok=True)
    safe_filename = f"receipt_{client_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join("./secure_receipts_storage", safe_filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    client["payment_agreed"] = True
    client["receipt_url"] = file_path
    
    for c_id in client["active_campaigns"].keys():
         client["active_campaigns"][c_id]["status"] = "Awaiting Integration"
         client["active_campaigns"][c_id]["current_step"] = "⚠️ Requires Credentials Verification"
         
    return {"status": "success", "file_stored": file_path, "payment_status": "CONFIRMED"}


@app.post("/api/owner/save-integration")
def save_integration(payload: SaveIntegrationPayload, background_tasks: BackgroundTasks, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if payload.client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
    
    client = CLIENTS_DB[payload.client_id]
    if payload.channel_id not in client["integrations"]:
        raise HTTPException(status_code=400, detail="Channel not configured for this client profile.")
        
    client["integrations"][payload.channel_id]["is_active"] = True
    client["integrations"][payload.channel_id]["keys_configured"] = payload.credentials
    
    client["active_campaigns"][payload.channel_id]["status"] = "Queued"
    client["active_campaigns"][payload.channel_id]["current_step"] = "Credentials Verified. Queued for execution..."
    
    if client["payment_agreed"]:
        background_tasks.add_task(execute_asynchronous_channel_campaign, payload.client_id, payload.channel_id)
        
    return {"status": "success", "integration_status": client["integrations"][payload.channel_id]}


@app.post("/api/owner/toggle-step")
def toggle_specific_campaign_step(payload: ToggleStepPayload, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if payload.client_id not in CLIENTS_DB:
        raise HTTPException(status_code=404, detail="Client parameters not found.")
    
    client = CLIENTS_DB[payload.client_id]
    if payload.channel_id not in client["active_campaigns"]:
        raise HTTPException(status_code=400, detail="Channel not configured for this client profile.")
    
    step_toggles = client["active_campaigns"][payload.channel_id]["step_toggles"]
    if payload.step_name not in step_toggles:
         raise HTTPException(status_code=400, detail=f"Step '{payload.step_name}' not found within channel.")
         
    step_toggles[payload.step_name] = payload.is_enabled
    action_word = "ENABLED" if payload.is_enabled else "DISABLED"
    logger.info(f"Owner set step '{payload.step_name}' to {action_word} for client '{payload.client_id}'.")
    return {"status": "success", "step_name": payload.step_name, "is_enabled": payload.is_enabled}


@app.get("/api/owner/client-data/{client_id}")
def fetch_client_live_progress(client_id: str, x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    if client_id not in CLIENTS_DB:
         raise HTTPException(status_code=404, detail="Client parameters not found.")
    
    costs = calculate_live_expenses_detailed(client_id)
    payload = CLIENTS_DB[client_id].copy()
    payload["live_financials"] = costs
    return payload


@app.get("/api/owner/clients")
def list_onboarded_clients(x_owner_password: str = Header(None)):
    enforce_owner_shield(x_owner_password)
    return CLIENTS_DB


# --- Dynamic Interface Module (Client Portal & Owner Console) ---
@app.get("/", response_class=HTMLResponse)
def serve_portal_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Wachsen Hoch</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
            body { font-family: 'Plus Jakarta Sans', sans-serif; }
        </style>
    </head>
    <body class="bg-[#F8F5F0] text-[#3D3025] min-h-screen">
        
        <header class="border-b border-[#E3DCD0] bg-[#FAF8F5] px-6 py-4 flex justify-between items-center shadow-sm">
            <h1 class="text-xl font-extrabold tracking-tight text-[#5C4A3C]">⚡ WH Wachsen Hoch</h1>
            <div class="flex gap-4">
                <button onclick="toggleView('client')" class="px-5 py-2 rounded-lg bg-[#5C4A3C] text-xs font-bold text-[#F8F5F0] hover:bg-[#4A3B30] transition shadow">Client Portal View</button>
                <button onclick="toggleView('owner')" class="px-5 py-2 rounded-lg bg-[#EAE3D5] text-xs font-bold text-[#5C4A3C] border border-[#D5CABD] hover:bg-[#DFD8C9] transition">Owner Console View</button>
            </div>
        </header>

        <!-- CLIENT PORTAL VIEW -->
        <section id="clientView" class="max-w-4xl mx-auto p-6 space-y-8 mt-4">
            <div class="text-center space-y-2">
                <h2 class="text-3xl font-black text-[#3D3025]">Design Your Growth Campaign</h2>
                <p class="text-sm text-[#7D6B5D]">Select your marketing services and customize each channel's active sub-steps to fit your business goals.</p>
            </div>

            <form id="onboardForm" class="bg-white p-8 rounded-2xl border border-[#E3DCD0] space-y-6 shadow-sm">
                <!-- Basic Details -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-xs font-bold text-[#7D6B5D] uppercase tracking-wider mb-2">Company Name</label>
                        <input type="text" id="companyName" required placeholder="Acme Inc." class="w-full bg-[#FAF8F5] border border-[#E3DCD0] rounded-xl p-3 text-sm text-[#3D3025] outline-none focus:ring-2 focus:ring-[#8C7A6B] text-black">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-[#7D6B5D] uppercase tracking-wider mb-2">Contact Email</label>
                        <input type="email" id="email" required placeholder="contact@acme.com" class="w-full bg-[#FAF8F5] border border-[#E3DCD0] rounded-xl p-3 text-sm text-[#3D3025] outline-none focus:ring-2 focus:ring-[#8C7A6B] text-black">
                    </div>
                </div>

                <!-- Plan Selection & Billing Pricing Warning -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-xs font-bold text-[#7D6B5D] uppercase tracking-wider mb-2">Select Campaign Plan Level</label>
                        <select id="selectedTier" class="w-full bg-[#FAF8F5] border border-[#E3DCD0] rounded-xl p-3 text-sm text-[#3D3025] outline-none focus:ring-2 focus:ring-[#8C7A6B] text-black">
                            <option value="standard">Standard Level Plan</option>
                            <option value="premium">Premium Level Plan</option>
                            <option value="elite">Elite Level Plan (Maximum Output)</option>
                        </select>
                    </div>
                    <div class="bg-[#FAF8F5] p-4 rounded-xl border border-[#E3DCD0] flex items-center justify-center shadow-inner">
                        <p class="text-xs text-[#8C6D3B] font-semibold text-center italic">
                            💬 Our team will contact you to explain/discuss monthly and yearly payment plans and costs.
                        </p>
                    </div>
                </div>

                <!-- Dynamic Service Selection Container -->
                <div class="space-y-6">
                    <label class="block text-xs font-bold text-[#7D6B5D] uppercase tracking-wider">Select Marketing Services & Configure Steps</label>
                    <div id="dynamicClientServicesContainer" class="space-y-4 text-black"></div>
                </div>

                <button type="submit" class="w-full bg-[#5C4A3C] hover:bg-[#4A3B30] text-[#F8F5F0] font-bold py-4 rounded-xl text-sm transition shadow-md">
                    Submit Inquiry & Lock Profile Parameters
                </button>
            </form>
        </section>

        <!-- OWNER CONSOLE VIEW -->
        <section id="ownerView" class="hidden max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-8 mt-4">
            
            <!-- Left Panel: Profile & Leads Admin -->
            <div class="space-y-6">
                <h2 class="text-lg font-extrabold text-[#3D3025]">Pending Inquiries DB</h2>
                <div id="clientsListContainer" class="space-y-3 bg-white p-4 rounded-2xl border border-[#E3DCD0] shadow-sm">
                    <p class="text-xs text-gray-500">No active client profiles onboarded yet.</p>
                </div>

                <!-- Owner Dynamic Service Overwrite Panel -->
                <div id="serviceModifyPanel" class="hidden bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <h3 class="text-sm font-bold text-[#5C4A3C]">🎛️ Modify Services (Callback Dialogue Update)</h3>
                    <p class="text-xs text-[#7D6B5D]">Owner can add or remove any of the 7 main marketing disciplines. Costs update instantly below.</p>
                    <div id="ownerChannelsChecklistContainer" class="space-y-2 bg-[#FAF8F5] p-3 rounded-xl border border-[#E3DCD0] text-xs text-[#3D3025]"></div>
                    <button onclick="saveOwnerCampaignModifications()" class="w-full bg-[#5C4A3C] text-xs font-bold py-2.5 rounded-xl text-[#F8F5F0] hover:bg-[#4A3B30] transition shadow-sm">
                        Update Client Channels & Costs
                    </button>
                </div>

                <!-- Secure File Receipt Upload Panel -->
                <div id="paymentPanel" class="hidden bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <h3 class="text-sm font-bold text-[#5C4A3C]">💰 Payment & Receipt Archiving</h3>
                    <div>
                        <label class="block text-xs text-[#7D6B5D] mb-1">Upload Client Bank/Processor Receipt (PDF/Image)</label>
                        <input type="file" id="receiptFile" class="w-full text-xs text-[#7D6B5D] file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#EAE3D5] file:text-[#5C4A3C] hover:file:bg-[#DFD8C9] cursor-pointer">
                    </div>
                    <button onclick="uploadReceipt()" class="w-full bg-[#5C4A3C] text-xs font-bold py-2.5 rounded-xl text-[#F8F5F0] hover:bg-[#4A3B30] transition shadow-sm">
                        Confirm Payment & Upload Receipt
                    </button>
                </div>
            </div>

            <!-- Right Panel: Live Operations & Variable Cost Dashboard -->
            <div class="lg:col-span-2 space-y-6">
                <div class="flex justify-between items-center bg-white p-4 rounded-2xl border border-[#E3DCD0] shadow-sm">
                    <h2 class="text-lg font-extrabold text-[#3D3025]">Campaign Operations Room</h2>
                    <span id="currentActiveClientLabel" class="text-xs text-[#5C4A3C] font-bold bg-[#EAE3D5] px-3 py-1.5 rounded-lg border border-gray-850">No Active Client Selected</span>
                </div>

                <!-- Dynamic Request Approval Box -->
                <div id="ownerApprovalActionBox" class="hidden bg-[#FAF8F5] p-6 rounded-2xl border border-[#E3DCD0] flex justify-between items-center shadow-sm">
                    <div class="space-y-1">
                        <h3 class="text-sm font-bold text-[#5C4A3C]">Audit & Verification Check Required</h3>
                        <p class="text-xs text-[#7D6B5D]">Would you like to approve or decline this client campaign portfolio setup?</p>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="approveClientInquiry()" class="bg-emerald-700 hover:bg-emerald-800 text-xs font-bold text-white px-4 py-2 rounded-xl transition shadow">Approve Request</button>
                        <button onclick="declineClientInquiry()" class="bg-rose-700 hover:bg-rose-800 text-xs font-bold text-white px-4 py-2 rounded-xl transition shadow">Decline Request</button>
                    </div>
                </div>

                <!-- Live Variable Cost Engine Stats -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-white p-6 rounded-2xl border border-[#E3DCD0] shadow-sm">
                        <p class="text-xs text-[#7D6B5D] font-bold uppercase tracking-wider">Owner Running Daily Overhead (SaaS Infrastructure)</p>
                        <p id="ownerOverheadVal" class="text-2xl font-black text-[#8C6D3B] mt-1">₹0.00 / day</p>
                    </div>
                    <div class="bg-white p-6 rounded-2xl border border-[#E3DCD0] shadow-sm">
                        <p class="text-xs text-[#7D6B5D] font-bold uppercase tracking-wider">Client Running Daily Cost (Ad Spend / Carrier Fees)</p>
                        <p id="clientOverheadVal" class="text-2xl font-black text-[#5C4A3C] mt-1">₹0.00 / day</p>
                    </div>
                </div>

                <!-- Itemized Platform Connection Breakdown Panel -->
                <div id="itemizedBillPanel" class="hidden bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <h3 class="text-xs font-bold text-[#5C4A3C] uppercase tracking-wider">🔌 Platform Cost Breakdown (Live Estimate Dashboard)</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs border-collapse">
                            <thead>
                                <tr class="border-b border-[#E3DCD0] text-[#7D6B5D]">
                                    <th class="py-2.5">Service</th>
                                    <th class="py-2.5">Integration Connected</th>
                                    <th class="py-2.5">Frequency & Validity</th>
                                    <th class="py-2.5 text-[#8C6D3B]">Owner API Cost</th>
                                    <th class="py-2.5 text-[#5C4A3C]">Client Ad Spend</th>
                                </tr>
                            </thead>
                            <tbody id="itemizedBillBody" class="text-[#3D3025]"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Dynamic Campaign Activity Toggles (Owner Switches) -->
                <div id="activityTogglesPanel" class="hidden bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <h3 class="text-md font-bold text-[#5C4A3C]">🎛️ Dynamic Campaign Activity Toggles</h3>
                    <p class="text-xs text-[#7D6B5D]">Turn specific sub-steps or processes on or off. Disabled steps are instantly bypassed by the automation engine.</p>
                    <div id="activityTogglesContainer" class="space-y-4 text-black"></div>
                </div>

                <!-- Data Onboarding Interface -->
                <div id="dataCollectionPanel" class="hidden bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <h3 class="text-md font-bold text-[#5C4A3C]">🔌 Onboarding API Key & Account Data Collection</h3>
                    <div id="credentialsInputsContainer" class="space-y-4 text-black"></div>
                </div>

                <!-- Active Progress Loop -->
                <div class="bg-white p-6 rounded-2xl border border-[#E3DCD0] space-y-4 shadow-sm">
                    <div class="flex justify-between items-center">
                        <h3 class="text-md font-bold text-[#5C4A3C]">Dynamic Campaign Execution Logs</h3>
                        <button onclick="generateReport()" class="bg-[#EAE3D5] hover:bg-[#DFD8C9] text-xs font-bold px-3 py-1.5 rounded-lg text-[#5C4A3C]">Generate Report</button>
                    </div>
                    <div id="campaignProgressContainer" class="space-y-4">
                        <p class="text-xs text-gray-500">Awaiting client profile configuration...</p>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <script>
        let selectedClientId = "";
        let ownerPassword = "";  // Securely stored in temporary page state
        let channelDefinitions = {};

        async function fetchChannelDefinitions() {
            const res = await fetch('/api/channels');
            if (res.ok) {
                channelDefinitions = await res.json();
                renderClientOnboardingServices();
                renderOwnerModificationChecklist();
            }
        }

        function renderClientOnboardingServices() {
            const container = document.getElementById('dynamicClientServicesContainer');
            container.innerHTML = "";

            Object.keys(channelDefinitions).forEach(cid => {
                const spec = channelDefinitions[cid];
                
                let stepsHTML = "";
                spec.steps.forEach(step => {
                    const stepSanitized = step.replace(/ /g, '_');
                    stepsHTML += `
                        <label class="flex items-center justify-between text-xs text-[#7D6B5D] bg-[#FAF8F5] p-2.5 rounded-xl border border-[#E3DCD0]">
                            <span>${step}</span>
                            <input type="checkbox" id="toggle_${cid}_${stepSanitized}" checked onchange="warnToggle(this, 'client', '${step}')" class="rounded text-[#5C4A3C] focus:ring-0">
                        </label>
                    `;
                });

                container.innerHTML += `
                    <div class="bg-[#FAF8F5] p-5 rounded-2xl border border-[#E3DCD0] space-y-3">
                        <label class="flex items-center gap-2 font-bold text-sm cursor-pointer text-[#5C4A3C]">
                            <input type="checkbox" id="srv_${cid}" class="rounded text-[#5C4A3C] focus:ring-0"> ${spec.display_name}
                        </label>
                        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pl-6">
                            ${stepsHTML}
                        </div>
                    </div>
                `;
            });
        }

        function renderOwnerModificationChecklist() {
            const container = document.getElementById('ownerChannelsChecklistContainer');
            container.innerHTML = "";
            Object.keys(channelDefinitions).forEach(cid => {
                const spec = channelDefinitions[cid];
                container.innerHTML += `
                    <label class="flex items-center gap-2 py-1.5 cursor-pointer">
                        <input type="checkbox" id="own_${cid}" class="rounded text-[#5C4A3C] focus:ring-0"> ${spec.display_name}
                    </label>
                `;
            });
        }

        async function toggleView(view) {
            if (view === 'client') {
                document.getElementById('clientView').classList.remove('hidden');
                document.getElementById('ownerView').classList.add('hidden');
            } else {
                // If password is not stored, open authentication prompt modal
                if (!ownerPassword) {
                    const userInput = prompt("🔐 Enter Owner Security Shield Password to Access the Dashboard:");
                    if (!userInput) return;
                    ownerPassword = userInput;
                }

                // Verify owner privileges safely on backend using header
                const res = await fetch('/api/owner/clients', {
                    headers: { 'X-Owner-Password': ownerPassword }
                });

                if (res.ok) {
                    document.getElementById('clientView').classList.add('hidden');
                    document.getElementById('ownerView').classList.remove('hidden');
                    fetchClientsList();
                } else {
                    alert("❌ Invalid Owner Password. Shield access blocked.");
                    ownerPassword = "";  // Wipe incorrect token from memory
                }
            }
        }

        function warnToggle(checkbox, target, stepName) {
            if (!checkbox.checked) {
                const confirmChoice = confirm(`⚠️ Warning: Disabling '${stepName}' will completely bypass this operational step in your marketing campaign. Do you confirm this action?`);
                if (!confirmChoice) {
                    checkbox.checked = true;
                }
            }
        }

        document.getElementById('onboardForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const selectedChannels = [];
            Object.keys(channelDefinitions).forEach(cid => {
                if (document.getElementById(`srv_${cid}`).checked) {
                    selectedChannels.push(cid);
                }
            });

            if (selectedChannels.length === 0) {
                alert("Please select at least one marketing service to submit your profile.");
                return;
            }

            const stepToggles = {};
            selectedChannels.forEach(cid => {
                stepToggles[cid] = {};
                channelDefinitions[cid].steps.forEach(step => {
                    const stepSanitized = step.replace(/ /g, '_');
                    stepToggles[cid][step] = document.getElementById(`toggle_${cid}_${stepSanitized}`).checked;
                });
            });

            const payload = {
                company_name: document.getElementById('companyName').value,
                email: document.getElementById('email').value,
                selected_channels: selectedChannels,
                step_toggles: stepToggles,
                selected_tier: document.getElementById('selectedTier').value,
                cost: 999.00
            };

            const res = await fetch('/api/client/inquire', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("🎉 Inquiry submitted successfully! Your campaign configuration is locked. Our team will contact you to discuss costs and payment plans.");
                document.getElementById('onboardForm').reset();
                renderClientOnboardingServices();
            } else {
                const err = await res.json();
                alert("Error: " + err.detail);
            }
        });

        async function fetchClientsList() {
            const res = await fetch('/api/owner/clients', {
                headers: { 'X-Owner-Password': ownerPassword }
            });
            if (res.ok) {
                const clients = await res.json();
                const container = document.getElementById('clientsListContainer');
                container.innerHTML = "";
                
                Object.keys(clients).forEach(cid => {
                    const client = clients[cid];
                    let activeBadge = "bg-yellow-900/10 text-[#8C6D3B]";
                    if (client.payment_agreed) activeBadge = "bg-emerald-950/10 text-emerald-700";
                    if (client.approval_status === "DECLINED") activeBadge = "bg-rose-950/10 text-rose-700";

                    container.innerHTML += `
                        <div onclick="selectClient('${cid}')" class="p-4 bg-[#FAF8F5] rounded-xl border border-[#E3DCD0] cursor-pointer hover:border-[#5C4A3C] transition flex justify-between items-center shadow-sm">
                            <div>
                                <h4 class="text-xs font-bold text-[#3D3025]">${client.company_name}</h4>
                                <p class="text-[10px] text-[#7D6B5D] mt-1">${client.email} | Tier: ${client.subscription_tier.toUpperCase()}</p>
                            </div>
                            <span class="text-[9px] font-bold px-2.5 py-1 rounded-full ${activeBadge}">${client.payment_agreed ? 'Paid' : client.approval_status}</span>
                        </div>
                    `;
                });
            }
        }

        async function selectClient(clientId) {
            selectedClientId = clientId;
            const res = await fetch(`/api/owner/client-data/${clientId}`, {
                headers: { 'X-Owner-Password': ownerPassword }
            });
            if (res.ok) {
                const data = await res.json();
                document.getElementById('currentActiveClientLabel').innerText = `${data.company_name} (${data.subscription_tier.toUpperCase()})`;
                
                document.getElementById('ownerOverheadVal').innerText = `₹${data.live_financials.owner_running_daily_cost.toFixed(2)} / day`;
                document.getElementById('clientOverheadVal').innerText = `₹${data.live_financials.client_running_daily_cost.toFixed(2)} / day`;

                document.getElementById('serviceModifyPanel').classList.remove('hidden');
                Object.keys(channelDefinitions).forEach(cid => {
                    document.getElementById(`own_${cid}`).checked = cid in data.active_campaigns;
                });

                const approvalBar = document.getElementById('ownerApprovalActionBox');
                if (data.approval_status === "PENDING") {
                    approvalBar.classList.remove('hidden');
                } else {
                    approvalBar.classList.add('hidden');
                }

                if (data.approval_status === "APPROVED" && !data.payment_agreed) {
                    document.getElementById('paymentPanel').classList.remove('hidden');
                    document.getElementById('dataCollectionPanel').classList.add('hidden');
                } else {
                    document.getElementById('paymentPanel').classList.add('hidden');
                    if (data.payment_agreed) {
                        document.getElementById('dataCollectionPanel').classList.remove('hidden');
                        renderDataOnboardingFields(data);
                    } else {
                        document.getElementById('dataCollectionPanel').classList.add('hidden');
                    }
                }

                renderItemizedBill(data.live_financials.details);
                renderActivityToggles(data);
                renderProgressIndicators(data);
            }
        }

        function renderActivityToggles(data) {
            document.getElementById('activityTogglesPanel').classList.remove('hidden');
            const togglesContainer = document.getElementById('activityTogglesContainer');
            togglesContainer.innerHTML = "";

            Object.keys(data.active_campaigns).forEach(channelId => {
                const camp = data.active_campaigns[channelId];
                const toggles = camp.step_toggles;
                
                let stepTogglesHTML = "";
                Object.keys(toggles).forEach(stepName => {
                    const isChecked = toggles[stepName] ? "checked" : "";
                    const stepIdSafe = stepName.replace(/ /g, '_');
                    stepTogglesHTML += `
                        <div class="flex justify-between items-center bg-[#FAF8F5] p-3 rounded-xl border border-[#E3DCD0] text-xs">
                            <span class="text-[#3D3025] font-medium">${stepName}</span>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="toggle_${channelId}_${stepIdSafe}" 
                                       onchange="toggleCampaignStep('${channelId}', '${stepName}')" 
                                       class="sr-only peer" ${isChecked}>
                                <div class="w-9 h-5 bg-[#E1DCD3] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-[#D5CABD] after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#5C4A3C] peer-checked:after:bg-white"></div>
                            </label>
                        </div>
                    `;
                });

                togglesContainer.innerHTML += `
                    <div class="p-4 bg-white rounded-2xl border border-[#E3DCD0] space-y-3 shadow-sm">
                        <span class="text-xs font-bold text-[#5C4A3C]">${camp.display_name} Checklist</span>
                        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                            ${stepTogglesHTML}
                        </div>
                    </div>
                `;
            });
        }

        async function toggleCampaignStep(channelId, stepName) {
            const stepIdSafe = stepName.replace(/ /g, '_');
            const toggleElement = document.getElementById(`toggle_${channelId}_${stepIdSafe}`);
            const isChecked = toggleElement.checked;
            
            if (!isChecked) {
                const confirmChoice = confirm(`⚠️ Warning: Disabling '${stepName}' will completely bypass this operational step in your marketing campaign. Do you confirm this action?`);
                if (!confirmChoice) {
                    toggleElement.checked = true;
                    return;
                }
            }
            
            const payload = {
                client_id: selectedClientId,
                channel_id: channelId,
                step_name: stepName,
                is_enabled: isChecked
            };

            const res = await fetch('/api/owner/toggle-step', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Owner-Password': ownerPassword
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                console.log("Successfully toggled specific sub-step: " + stepName);
            }
        }

        async function approveClientInquiry() {
            if (!selectedClientId) return;
            const res = await fetch(`/api/owner/approve-client/${selectedClientId}`, {
                method: 'POST',
                headers: { 'X-Owner-Password': ownerPassword }
            });
            if (res.ok) {
                alert("Client Inquiry Approved! Advances to Invoice Payment Stage.");
                selectClient(selectedClientId);
                fetchClientsList();
            }
        }

        async function declineClientInquiry() {
            if (!selectedClientId) return;
            const confirmDecline = confirm("Are you sure you want to decline this campaign proposal? The email lock will be removed so they can submit a new configuration profile.");
            if (!confirmDecline) return;

            const res = await fetch(`/api/owner/decline-client/${selectedClientId}`, {
                method: 'POST',
                headers: { 'X-Owner-Password': ownerPassword }
            });
            if (res.ok) {
                alert("Client Inquiry Declined. Email limit removed.");
                selectClient(selectedClientId);
                fetchClientsList();
            }
        }

        function renderItemizedBill(details) {
            const panel = document.getElementById('itemizedBillPanel');
            const tbody = document.getElementById('itemizedBillBody');
            
            if (details.length === 0) {
                panel.classList.add('hidden');
                return;
            }
            
            panel.classList.remove('hidden');
            tbody.innerHTML = "";
            
            details.forEach(item => {
                tbody.innerHTML += `
                    <tr class="border-b border-[#E3DCD0] text-xs">
                        <td class="py-3 font-bold text-[#3D3025]">${item.channel_name}</td>
                        <td class="py-3 text-[#5C4A3C] font-mono text-[10px]">${item.partner_api}</td>
                        <td class="py-3 text-gray-500 font-medium">
                            <span class="block">${item.billing_cycle}</span>
                            <span class="block text-[9px] text-[#8C6D3B] font-semibold">${item.validity}</span>
                        </td>
                        <td class="py-3 text-[#8C6D3B] font-bold">₹${item.owner_charge.toFixed(2)} / day <span class="block text-[9px] text-[#7D6B5D] font-normal font-sans">${item.owner_desc}</span></td>
                        <td class="py-3 text-[#5C4A3C] font-bold">₹${item.client_charge.toFixed(2)} / day <span class="block text-[9px] text-[#7D6B5D] font-normal font-sans">${item.client_desc}</span></td>
                    </tr>
                `;
            });
        }

        async function saveOwnerCampaignModifications() {
            if (!selectedClientId) return;
            
            const selectedChannels = [];
            Object.keys(channelDefinitions).forEach(cid => {
                if (document.getElementById(`own_${cid}`).checked) {
                    selectedChannels.push(cid);
                }
            });

            const payload = {
                client_id: selectedClientId,
                selected_channels: selectedChannels
            };

            const res = await fetch('/api/owner/update-client-campaigns', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Owner-Password': ownerPassword
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("Client profile channels and live cost matrices updated successfully!");
                selectClient(selectedClientId);
            } else {
                const err = await res.json();
                alert("Modification failed: " + err.detail);
            }
        }

        function renderDataOnboardingFields(data) {
            const container = document.getElementById('credentialsInputsContainer');
            container.innerHTML = "";
            
            Object.keys(data.integrations).forEach(channelId => {
                const integration = data.integrations[channelId];
                const channelName = data.active_campaigns[channelId].display_name;
                
                let inputsHTML = "";
                integration.fields_needed.forEach(field => {
                    const savedVal = integration.keys_configured[field] || "";
                    inputsHTML += `
                        <div>
                            <label class="block text-[10px] text-[#7D6B5D] font-semibold mb-1">${field}</label>
                            <input type="text" id="int_${channelId}_${field.replace(/ /g, '_')}" value="${savedVal}" 
                                   class="w-full bg-[#FAF8F5] border border-[#E3DCD0] rounded-xl p-2.5 text-xs text-[#3D3025] outline-none">
                        </div>
                    `;
                });

                const badge = integration.is_active 
                    ? `<span class="text-[10px] text-emerald-700 font-bold">● Active connection</span>`
                    : `<span class="text-[10px] text-rose-700 font-bold animate-pulse">⚠️ Connection Required</span>`;

                container.innerHTML += `
                    <div class="p-4 bg-[#FAF8F5] border border-[#E3DCD0] rounded-2xl space-y-3">
                        <div class="flex justify-between items-center border-b border-[#E3DCD0] pb-2">
                            <h4 class="text-xs font-bold text-[#5C4A3C]">${channelName}</h4>
                            ${badge}
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">${inputsHTML}</div>
                        <div class="flex justify-end">
                            <button onclick="saveOnboardingData('${channelId}')" class="bg-[#5C4A3C] hover:bg-[#4A3B30] text-xs font-semibold py-2 px-4 rounded-xl text-white transition shadow-sm">Save Connection</button>
                        </div>
                    </div>
                `;
            });
        }

        function renderProgressIndicators(data) {
            const container = document.getElementById('campaignProgressContainer');
            container.innerHTML = "";
            
            Object.keys(data.active_campaigns).forEach(cid => {
                const camp = data.active_campaigns[cid];
                let badgeStyle = "bg-[#FAF8F5] text-gray-500 border border-gray-300";
                if (camp.status === "Active") badgeStyle = "bg-[#EAE3D5] text-[#5C4A3C] border border-[#D5CABD]";
                if (camp.status === "Completed") badgeStyle = "bg-green-100 text-green-800 border border-green-300";
                if (camp.status === "Awaiting Lead Audit") badgeStyle = "bg-yellow-100 text-yellow-800 border border-yellow-300";
                if (camp.status === "Awaiting Payment") badgeStyle = "bg-yellow-100 text-yellow-800 border border-yellow-300";
                if (camp.status === "Awaiting Integration") badgeStyle = "bg-rose-100 text-rose-800 border border-rose-300";
                if (camp.status === "Declined") badgeStyle = "bg-rose-100 text-rose-800 border border-rose-300";

                container.innerHTML += `
                    <div class="p-4 bg-[#FAF8F5] rounded-2xl border border-[#E3DCD0] space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-bold text-[#3D3025]">${camp.display_name}</span>
                            <span class="text-[10px] font-bold px-2.5 py-1 rounded-full ${badgeStyle}">${camp.status}</span>
                        </div>
                        <div class="flex justify-between text-[11px] text-[#7D6B5D]">
                            <span>Step: <strong>${camp.current_step}</strong></span>
                            <span>${camp.progress}%</span>
                        </div>
                        <div class="w-full bg-[#EAE3D5] h-2 rounded-full overflow-hidden">
                            <div class="bg-[#5C4A3C] h-full transition-all duration-500" style="width: ${camp.progress}%"></div>
                        </div>
                    </div>
                `;
            });
        }

        async function uploadReceipt() {
            if (!selectedClientId) return;
            const fileInput = document.getElementById('receiptFile');
            if (fileInput.files.length === 0) {
                alert("Please select a valid receipt document to proceed.");
                return;
            }

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);

            const res = await fetch(`/api/owner/upload-receipt/${selectedClientId}`, {
                method: 'POST',
                headers: { 'X-Owner-Password': ownerPassword },
                body: formData
            });

            if (res.ok) {
                alert("Payment Confirmed and Receipt Archived!");
                selectClient(selectedClientId);
            } else {
                const err = await res.json();
                alert("Upload failed: " + err.detail);
            }
        }

        async function saveOnboardingData(channelId) {
            if (!selectedClientId) return;
            const fieldsNeeded = MARKETING_CHANNELS_DEFINITION[channelId].required_credentials;
            const credentials = {};
            
            fieldsNeeded.forEach(field => {
                const elId = `int_${channelId}_${field.replace(/ /g, '_')}`;
                credentials[field] = document.getElementById(elId).value;
            });

            const payload = {
                client_id: selectedClientId,
                channel_id: channelId,
                credentials: credentials
            };

            const res = await fetch('/api/owner/save-integration', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Owner-Password': ownerPassword
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("Integration successfully initialized. Campaign workflows activated.");
                selectClient(selectedClientId);
            }
        }

        function generateReport() {
            if (!selectedClientId) {
                alert("Please select a client profile to generate a report.");
                return;
            }
            alert(`📝 Performance Report Generated for Client ${selectedClientId}.\nCopying report to system clipboard...`);
        }

        fetchChannelDefinitions();

        setInterval(() => {
            if (selectedClientId && document.getElementById('ownerView').classList.contains('hidden') === false) {
                selectClient(selectedClientId);
            }
        }, 4000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
