# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Any
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import node, Edge, START, Workflow
from google.adk.events import Event, RequestInput
from google.adk.tools import AgentTool, McpToolset
from mcp import StdioServerParameters

import json
from datetime import datetime, timezone
from app.config import config
from app.security import scrub_pii, detect_injection, security_audit

# 1. State Schema
class AyushMitraState(BaseModel):
    query: str = ""
    route_decision: str = ""
    security_check_passed: bool = True
    audit_log: list[str] = Field(default_factory=list)
    hospital_search_results: str = ""
    prescription_simplification: str = ""
    human_reply: str = ""

# 2. Wire MCP Server
mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command="python",
        args=["-m", "app.mcp_server"]
    )
)

# 3. Custom escalate_to_human tool
def escalate_to_human(ctx: Any) -> str:
    """Escalates the current healthcare query to a human representative."""
    ctx.route = "human"
    return "Routing your request to a human representative."

# 4. Define Specialized Sub-Agents
hospital_finder = LlmAgent(
    name="hospital_finder",
    model=Gemini(model=config.model),
    instruction=(
        "You are the AyushMitra Hospital Finder, helping users find Ayushman Bharat empaneled hospitals.\n"
        "Use the tools provided (e.g. `search_hospitals`, `check_eligibility`) to find hospitals aligned with user specialty and region.\n"
        "Respond with a clear list of hospitals, including contact details and specialty alignment."
    ),
    tools=[mcp_toolset]
)

prescription_simplifier = LlmAgent(
    name="prescription_simplifier",
    model=Gemini(model=config.model),
    instruction=(
        "You are the AyushMitra Prescription Simplifier.\n"
        "Your role is to translate medical prescriptions and explain dosage instructions in simple terms.\n"
        "Use the tools provided (e.g. `simplify_terms`) to decode complex jargon.\n"
        "Structure the output clearly with: 1. Medicine Name, 2. Dosage (when/how), 3. Simple translation (Hindi/regional language if requested).\n"
        "Ensure critical warnings are highlighted."
    ),
    tools=[mcp_toolset]
)

# 5. Define Orchestrator Agent
orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model=config.model),
    instruction=(
        "You are the AyushMitra Orchestrator, an AI assistant helping users navigate public healthcare in India.\n"
        "Your task is to understand the user's intent and delegate to the appropriate specialized sub-agent:\n"
        "- For finding Ayushman Bharat empanelled hospitals, locations, or medical specialties, use the `hospital_finder` tool.\n"
        "- For translating prescriptions, explaining medicine dosages, and simplifying medical terms, use the `prescription_simplifier` tool.\n"
        "- If the user asks for direct human help, or if you cannot satisfy their request, call the `escalate_to_human` tool.\n"
        "Provide a clear, polite summary of the sub-agent's response or any intermediate state."
    ),
    tools=[
        AgentTool(hospital_finder),
        AgentTool(prescription_simplifier),
        escalate_to_human
    ]
)

# 6. Define Workflow Node Functions
async def _security_checkpoint(ctx: Any, node_input: str) -> str:
    ctx.state["query"] = node_input
    
    # 1. PII Scrubbing
    scrubbed_input = scrub_pii(node_input)
    ctx.state["query"] = scrubbed_input
    
    # Audit trail details structure
    audit_record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "original_query": node_input,
        "scrubbed_query": scrubbed_input,
        "checks": {}
    }
    
    # 2. Prompt Injection Check
    injection_detected = detect_injection(node_input) or detect_injection(scrubbed_input)
    audit_record["checks"]["injection_check"] = {
        "passed": not injection_detected,
        "details": "Potential prompt injection attempt identified" if injection_detected else "No injection pattern matched"
    }
    
    # 3. Domain-Specific Check
    # Ensure query contains healthcare/Ayushman-related terms
    healthcare_keywords = [
        "health", "doctor", "hospital", "medicine", "clinic", "disease", "symptom", 
        "prescription", "ayush", "wellness", "patient", "treatment", "cure", "vaccine", 
        "eligibility", "card", "scheme", "medical", "physician", "tablet", "syrup", "dosage"
    ]
    query_lower = node_input.lower()
    is_domain_match = any(kw in query_lower for kw in healthcare_keywords)
    
    # Let's consider query length or empty queries
    if len(query_lower.strip()) == 0:
        is_domain_match = False
        domain_details = "Empty query received"
    else:
        domain_details = "Query contains domain-relevant terminology" if is_domain_match else "Query is off-topic / not related to healthcare services"
        
    audit_record["checks"]["domain_check"] = {
        "passed": is_domain_match,
        "details": domain_details
    }
    
    # Determine final routing
    if injection_detected:
        ctx.route = "denied"
        ctx.state["security_check_passed"] = False
        decision = "DENIED_INJECTION"
        severity = "CRITICAL"
        result_message = "Request blocked due to security validation failure."
    elif not is_domain_match:
        ctx.route = "denied"
        ctx.state["security_check_passed"] = False
        decision = "DENIED_OFF_TOPIC"
        severity = "WARNING"
        result_message = "Request rejected: Query must be related to healthcare, hospitals, or prescriptions."
    else:
        ctx.route = "approved"
        ctx.state["security_check_passed"] = True
        decision = "APPROVED"
        severity = "INFO"
        result_message = scrubbed_input

    audit_record["decision"] = decision
    audit_record["severity"] = severity
    
    audit_json = json.dumps(audit_record)
    if "audit_log" not in ctx.state or ctx.state["audit_log"] is None:
        ctx.state["audit_log"] = []
    ctx.state["audit_log"].append(audit_json)
    security_audit(f"Decision: {decision}", audit_json)
    
    return result_message

@node
async def security_checkpoint(ctx: Any, node_input: str) -> str:
    return await _security_checkpoint(ctx, node_input)

@node
async def security_failed(ctx: Any, node_input: str) -> str:
    return "Request blocked: Security validation failed."

@node
async def human_help_node(ctx: Any, node_input: Any) -> Any:
    # If the user has already provided resume input, process it.
    if ctx.resume_inputs:
        user_reply = ctx.resume_inputs.get("human_reply")
        if user_reply:
            ctx.state["human_reply"] = user_reply
            ctx.route = "loop_back"
            return user_reply
            
    # Yield RequestInput to pause the workflow for human input
    return RequestInput(
        interrupt_id="human_reply",
        message="[AyushMitra] Manual review required. A healthcare representative is looking at your request. Please wait or respond..."
    )

@node
async def final_output(ctx: Any, node_input: Any) -> Any:
    return node_input

# 7. Compile Workflow Graph
ayush_mitra_workflow = Workflow(
    name="ayush_mitra_workflow",
    state_schema=AyushMitraState,
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=orchestrator, route="approved"),
        Edge(from_node=security_checkpoint, to_node=security_failed, route="denied"),
        Edge(from_node=orchestrator, to_node=human_help_node, route="human"),
        Edge(from_node=orchestrator, to_node=final_output, route="__DEFAULT__"),
        Edge(from_node=human_help_node, to_node=orchestrator, route="loop_back"),
        Edge(from_node=security_failed, to_node=final_output),
    ]
)

# 8. Declare ADK App
app = App(
    root_agent=ayush_mitra_workflow,
    name="app",
)
