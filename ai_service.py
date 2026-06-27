import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))

def classify_ticket(title: str, description: str) -> dict:
    """
    Classifies a support ticket using GPT-4o-mini.
    Returns category, priority, and token usage.
    """
    prompt = f"""You are a support ticket classification system. Classify the following support ticket.

Ticket Title: {title}
Ticket Description: {description}

Respond with ONLY a JSON object (no markdown, no explanation) in this exact format:
{{
    "category": "<one of: technical, billing, general, feature_request, other>",
    "priority": "<one of: low, medium, high, urgent>"
}}

Guidelines:
- technical: system issues, bugs, errors, crashes, network problems
- billing: payment, refund, invoice, subscription issues  
- feature_request: new feature suggestions or enhancements
- general: general inquiries, how-to questions
- other: anything that doesn't fit above
- urgent: system down, data loss, security breach
- high: major functionality broken, billing disputes
- medium: partial issues, general problems
- low: minor issues, feature requests, questions"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)

        valid_categories = ['technical', 'billing', 'general', 'feature_request', 'other']
        valid_priorities = ['low', 'medium', 'high', 'urgent']

        category = result.get('category', 'general')
        priority = result.get('priority', 'medium')

        if category not in valid_categories:
            category = 'general'
        if priority not in valid_priorities:
            priority = 'medium'

        return {
            'category': category,
            'priority': priority,
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens
        }

    except Exception as e:
        print(f"[AI classify error] {e}")
        # Fallback: rule-based if GPT fails
        text = (title + " " + description).lower()
        if any(word in text for word in ["down", "server", "crash", "critical", "error", "bug"]):
            return {"category": "technical", "priority": "high", "prompt_tokens": 0, "completion_tokens": 0}
        if any(word in text for word in ["payment", "refund", "invoice", "billing", "charge"]):
            return {"category": "billing", "priority": "high", "prompt_tokens": 0, "completion_tokens": 0}
        return {"category": "general", "priority": "medium", "prompt_tokens": 0, "completion_tokens": 0}
def generate_draft_response(ticket_title: str, ticket_description: str, previous_responses: list) -> dict:
    """
    Generates a draft response for an agent using GPT-4o-mini.
    previous_responses: list of dicts with 'role' (customer/agent) and 'message'
    Returns dict: { draft, prompt_tokens, completion_tokens }
    """
    convo_history = ""
    for r in previous_responses:
        role_label = "Customer" if r['role'] == 'customer' else "Support Agent"
        convo_history += f"\n{role_label}: {r['message']}"

    prompt = f"""You are a helpful customer support agent. Generate a professional, empathetic response to this support ticket.

Ticket Title: {ticket_title}
Original Issue: {ticket_description}

Conversation so far:{convo_history if convo_history else " (No previous responses)"}

Write a response that:
- Acknowledges the customer's issue
- Is professional but warm in tone
- Provides a helpful next step or solution
- Is concise (max 3-4 sentences)
- Does NOT use placeholder text like [your name]

Respond with ONLY the message text, no subject line, no greeting preamble."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )

        draft = response.choices[0].message.content.strip()

        return {
            'draft': draft,
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens
        }

    except Exception as e:
        print(f"[AI draft error] {e}")

    fallback = f"""
Thank you for contacting support regarding "{ticket_title}".

We have received your request and are currently reviewing the issue. Our team will investigate further and provide an update as soon as possible.

Please let us know if you have any additional information that may help us resolve this faster.
""".strip()

    return {
        'draft': fallback,
        'prompt_tokens': 0,
        'completion_tokens': 0
    }
