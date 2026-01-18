"""
Modifier library for synthetic conversation generation.

Modifiers affect conversation tone, dynamics, and characteristics.
They are independent of topic and language, applied as overlays.

Organized into 4 categories with ~100 modifiers total:
- User emotional state (~25)
- Agent behavior (~25)
- Conversation dynamics (~25)
- Technical factors (~25)
"""

from dataclasses import dataclass
from enum import Enum
import random


class ModifierCategory(str, Enum):
    USER_STATE = "user_state"
    AGENT_BEHAVIOR = "agent_behavior"
    DYNAMICS = "dynamics"
    TECHNICAL = "technical"


@dataclass
class Modifier:
    id: str
    category: ModifierCategory
    name: str
    description: str
    generation_notes: str  # Instructions for LLM generation

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "generation_notes": self.generation_notes,
        }


# =============================================================================
# USER EMOTIONAL STATE (~25 modifiers)
# =============================================================================

USER_STATE_MODIFIERS = [
    Modifier(
        "user_frustrated",
        ModifierCategory.USER_STATE,
        "Frustrated User",
        "User is frustrated or annoyed about their issue",
        "User speaks with impatience, may use short sentences, sighs, or express annoyance. "
        "They may reference previous failed attempts or how long they've been dealing with this."
    ),
    Modifier(
        "user_angry",
        ModifierCategory.USER_STATE,
        "Angry User",
        "User is visibly angry about the situation",
        "User speaks forcefully, may raise voice (indicated by caps or exclamation), "
        "demands immediate resolution, may threaten to cancel/leave."
    ),
    Modifier(
        "user_confused",
        ModifierCategory.USER_STATE,
        "Confused User",
        "User is confused and doesn't fully understand the situation",
        "User asks clarifying questions, may repeat information back incorrectly, "
        "uses phrases like 'I don't understand' or 'what does that mean?'"
    ),
    Modifier(
        "user_hurried",
        ModifierCategory.USER_STATE,
        "Rushed User",
        "User is in a hurry and wants quick resolution",
        "User speaks quickly, mentions time constraints ('I only have 5 minutes'), "
        "may cut agent off, wants to skip pleasantries and get to the point."
    ),
    Modifier(
        "user_elderly",
        ModifierCategory.USER_STATE,
        "Elderly User",
        "User is elderly and may need more patience and clear explanations",
        "User speaks slowly, may ask for things to be repeated, uses older terminology, "
        "may mention age-related context, needs step-by-step guidance."
    ),
    Modifier(
        "user_anxious",
        ModifierCategory.USER_STATE,
        "Anxious User",
        "User is worried or anxious about the situation",
        "User asks for reassurance, mentions worst-case scenarios, wants confirmation, "
        "may ask the same question multiple ways to be sure."
    ),
    Modifier(
        "user_friendly",
        ModifierCategory.USER_STATE,
        "Friendly/Chatty User",
        "User is warm and conversational",
        "User engages in small talk, is polite and patient, thanks the agent, "
        "may share personal context or stories, uses friendly language."
    ),
    Modifier(
        "user_skeptical",
        ModifierCategory.USER_STATE,
        "Skeptical User",
        "User is doubtful or distrustful",
        "User questions the agent's answers, asks for verification, "
        "may reference bad past experiences, wants things in writing."
    ),
    Modifier(
        "user_grateful",
        ModifierCategory.USER_STATE,
        "Grateful User",
        "User is appreciative and thankful",
        "User thanks the agent multiple times, expresses relief, "
        "may compliment the service or agent specifically."
    ),
    Modifier(
        "user_apologetic",
        ModifierCategory.USER_STATE,
        "Apologetic User",
        "User feels bad about calling or the situation",
        "User apologizes for the trouble, may downplay their issue, "
        "says 'sorry to bother you' or 'I know this is a dumb question'."
    ),
    Modifier(
        "user_demanding",
        ModifierCategory.USER_STATE,
        "Demanding User",
        "User has high expectations and is assertive",
        "User states exactly what they want, references their loyalty/spending, "
        "may ask for supervisor, expects exceptions to be made."
    ),
    Modifier(
        "user_distracted",
        ModifierCategory.USER_STATE,
        "Distracted User",
        "User is multitasking or has things going on in background",
        "User asks agent to repeat things, apologizes for background noise, "
        "may pause mid-sentence, mentions doing other things."
    ),
    Modifier(
        "user_tech_savvy",
        ModifierCategory.USER_STATE,
        "Tech-Savvy User",
        "User is technically knowledgeable",
        "User uses technical terminology correctly, may have already tried troubleshooting, "
        "wants to skip basic steps, understands explanations quickly."
    ),
    Modifier(
        "user_tech_challenged",
        ModifierCategory.USER_STATE,
        "Tech-Challenged User",
        "User struggles with technology",
        "User needs very basic explanations, may not know common terms, "
        "asks 'where is that button?', needs patient guidance."
    ),
    Modifier(
        "user_first_time",
        ModifierCategory.USER_STATE,
        "First-Time Caller",
        "User is calling for the first time",
        "User mentions this is their first time calling, doesn't know the process, "
        "may ask how things work, needs orientation."
    ),
    Modifier(
        "user_repeat_caller",
        ModifierCategory.USER_STATE,
        "Repeat Caller",
        "User has called about this issue before",
        "User references previous calls, may have case numbers, "
        "shows frustration if issue isn't resolved, knows the process."
    ),
    Modifier(
        "user_emotional",
        ModifierCategory.USER_STATE,
        "Emotional User",
        "User is dealing with an emotional situation",
        "User may be tearful or voice may shake, dealing with loss/hardship, "
        "needs empathy, issue may involve deceased family member."
    ),
    Modifier(
        "user_business",
        ModifierCategory.USER_STATE,
        "Business/Professional User",
        "User is calling in a professional capacity",
        "User speaks professionally, mentions business account or company, "
        "may need things for business purposes, focused and efficient."
    ),
    Modifier(
        "user_non_native",
        ModifierCategory.USER_STATE,
        "Non-Native Speaker",
        "User's first language is not English",
        "User may have accent or non-standard phrasing, may ask for clarification, "
        "simpler vocabulary may be used, occasional grammar variations."
    ),
    Modifier(
        "user_hearing_impaired",
        ModifierCategory.USER_STATE,
        "Hearing-Impaired User",
        "User has hearing difficulties",
        "User asks agent to speak up or repeat, may speak louder themselves, "
        "may prefer text/email follow-up."
    ),
    Modifier(
        "user_parent_with_kids",
        ModifierCategory.USER_STATE,
        "Parent with Kids",
        "User is dealing with children in background",
        "User apologizes for noise, may need to pause, talks to kids mid-conversation, "
        "may be distracted or hurried."
    ),
    Modifier(
        "user_tired",
        ModifierCategory.USER_STATE,
        "Tired/Exhausted User",
        "User sounds tired or exhausted",
        "User speaks slowly, may yawn or sigh, mentions being tired, "
        "may be less patient, wants quick resolution."
    ),
    Modifier(
        "user_long_time_customer",
        ModifierCategory.USER_STATE,
        "Long-Time Customer",
        "User emphasizes their loyalty and history",
        "User mentions years of being a customer, expects recognition, "
        "references past positive experiences, may expect special treatment."
    ),
    Modifier(
        "user_price_conscious",
        ModifierCategory.USER_STATE,
        "Price-Conscious User",
        "User is focused on costs and value",
        "User asks about prices, discounts, cheaper alternatives, "
        "compares to competitors, may try to negotiate."
    ),
]

# =============================================================================
# AGENT BEHAVIOR (~25 modifiers)
# =============================================================================

AGENT_BEHAVIOR_MODIFIERS = [
    Modifier(
        "agent_concise",
        ModifierCategory.AGENT_BEHAVIOR,
        "Concise Agent",
        "Agent provides brief, to-the-point responses",
        "Agent uses short sentences, doesn't over-explain, "
        "efficiently addresses the issue without filler."
    ),
    Modifier(
        "agent_warm",
        ModifierCategory.AGENT_BEHAVIOR,
        "Warm/Empathetic Agent",
        "Agent is warm, friendly, and shows empathy",
        "Agent uses phrases like 'I understand how frustrating that must be', "
        "offers reassurance, has a caring tone."
    ),
    Modifier(
        "agent_formal",
        ModifierCategory.AGENT_BEHAVIOR,
        "Formal/Professional Agent",
        "Agent maintains very professional demeanor",
        "Agent uses formal language, proper grammar, avoids contractions, "
        "maintains professional distance while being helpful."
    ),
    Modifier(
        "agent_casual",
        ModifierCategory.AGENT_BEHAVIOR,
        "Casual/Friendly Agent",
        "Agent has a relaxed, conversational style",
        "Agent uses casual language, contractions, may use light humor, "
        "feels more like talking to a friend."
    ),
    Modifier(
        "agent_apologetic",
        ModifierCategory.AGENT_BEHAVIOR,
        "Apologetic Agent",
        "Agent frequently apologizes for issues",
        "Agent says sorry multiple times, takes responsibility, "
        "acknowledges the customer's frustration."
    ),
    Modifier(
        "agent_thorough",
        ModifierCategory.AGENT_BEHAVIOR,
        "Thorough Agent",
        "Agent provides detailed, comprehensive responses",
        "Agent explains things fully, covers edge cases, "
        "may over-explain to ensure understanding."
    ),
    Modifier(
        "agent_clarifying",
        ModifierCategory.AGENT_BEHAVIOR,
        "Clarifying Agent",
        "Agent asks many clarifying questions",
        "Agent confirms understanding before proceeding, repeats back information, "
        "asks 'just to confirm...' or 'so what you're saying is...'"
    ),
    Modifier(
        "agent_solution_focused",
        ModifierCategory.AGENT_BEHAVIOR,
        "Solution-Focused Agent",
        "Agent focuses on finding solutions quickly",
        "Agent jumps to solutions, offers alternatives, "
        "moves conversation toward resolution efficiently."
    ),
    Modifier(
        "agent_by_the_book",
        ModifierCategory.AGENT_BEHAVIOR,
        "By-the-Book Agent",
        "Agent strictly follows policies and procedures",
        "Agent references policies, may not make exceptions, "
        "explains why certain things can't be done."
    ),
    Modifier(
        "agent_flexible",
        ModifierCategory.AGENT_BEHAVIOR,
        "Flexible Agent",
        "Agent is willing to make exceptions or find workarounds",
        "Agent says 'let me see what I can do', offers alternatives, "
        "willing to go above and beyond."
    ),
    Modifier(
        "agent_new_training",
        ModifierCategory.AGENT_BEHAVIOR,
        "New/Training Agent",
        "Agent is new and may need to check things",
        "Agent says 'let me check on that', may put customer on hold, "
        "asks for patience, may be less confident."
    ),
    Modifier(
        "agent_experienced",
        ModifierCategory.AGENT_BEHAVIOR,
        "Experienced Agent",
        "Agent is clearly experienced and knowledgeable",
        "Agent answers quickly and confidently, knows edge cases, "
        "may offer proactive suggestions."
    ),
    Modifier(
        "agent_patient",
        ModifierCategory.AGENT_BEHAVIOR,
        "Patient Agent",
        "Agent is very patient and understanding",
        "Agent doesn't rush, willing to explain multiple times, "
        "remains calm even with difficult customers."
    ),
    Modifier(
        "agent_efficient",
        ModifierCategory.AGENT_BEHAVIOR,
        "Efficient Agent",
        "Agent moves quickly through the call",
        "Agent is focused, doesn't waste time, "
        "moves to next steps promptly."
    ),
    Modifier(
        "agent_upselling",
        ModifierCategory.AGENT_BEHAVIOR,
        "Upselling Agent",
        "Agent tries to offer additional products/services",
        "Agent mentions upgrades, add-ons, or promotions, "
        "tries to add value while helping."
    ),
    Modifier(
        "agent_retention_focused",
        ModifierCategory.AGENT_BEHAVIOR,
        "Retention-Focused Agent",
        "Agent tries to keep customer from leaving",
        "Agent offers deals, asks about concerns, "
        "tries to address why customer wants to cancel."
    ),
    Modifier(
        "agent_technical",
        ModifierCategory.AGENT_BEHAVIOR,
        "Technical Agent",
        "Agent is in a technical support role",
        "Agent asks technical questions, may use jargon, "
        "walks through troubleshooting steps."
    ),
    Modifier(
        "agent_billing",
        ModifierCategory.AGENT_BEHAVIOR,
        "Billing Specialist Agent",
        "Agent specializes in billing issues",
        "Agent references account details, explains charges, "
        "can process payments and adjustments."
    ),
    Modifier(
        "agent_supervisor",
        ModifierCategory.AGENT_BEHAVIOR,
        "Supervisor/Manager",
        "Agent is a supervisor handling escalation",
        "Agent has more authority, can make exceptions, "
        "acknowledges previous issues, offers resolution."
    ),
    Modifier(
        "agent_callback",
        ModifierCategory.AGENT_BEHAVIOR,
        "Callback Agent",
        "Agent is returning a customer's call",
        "Agent references previous call or ticket, "
        "summarizes what was discussed, follows up."
    ),
    Modifier(
        "agent_multichannel",
        ModifierCategory.AGENT_BEHAVIOR,
        "Multichannel Agent",
        "Agent offers other contact methods",
        "Agent may offer to send email confirmation, "
        "suggests chat or app for certain tasks."
    ),
]

# =============================================================================
# CONVERSATION DYNAMICS (~25 modifiers)
# =============================================================================

DYNAMICS_MODIFIERS = [
    Modifier(
        "dynamics_interruption",
        ModifierCategory.DYNAMICS,
        "User Interrupts",
        "User interrupts the agent mid-sentence",
        "User cuts agent off, finishes agent's sentences, "
        "or starts talking before agent finishes."
    ),
    Modifier(
        "dynamics_agent_interrupts",
        ModifierCategory.DYNAMICS,
        "Agent Interrupts",
        "Agent interjects when user pauses",
        "Agent jumps in to help when user pauses or seems stuck, "
        "offers assistance mid-thought."
    ),
    Modifier(
        "dynamics_correction",
        ModifierCategory.DYNAMICS,
        "Self-Correction",
        "User corrects themselves mid-sentence",
        "User says 'actually, I mean...' or 'wait, no, it's...', "
        "changes information they're providing."
    ),
    Modifier(
        "dynamics_unprompted",
        ModifierCategory.DYNAMICS,
        "Unprompted Information",
        "User provides information before being asked",
        "User volunteers details like order number, name, etc. "
        "before agent requests them."
    ),
    Modifier(
        "dynamics_small_talk",
        ModifierCategory.DYNAMICS,
        "Small Talk",
        "Conversation includes casual chat",
        "Agent and user engage in brief pleasantries, "
        "comment on weather, or have light banter."
    ),
    Modifier(
        "dynamics_tangent",
        ModifierCategory.DYNAMICS,
        "Off-Topic Tangent",
        "User goes off on a tangent",
        "User starts talking about something unrelated, "
        "agent needs to redirect conversation."
    ),
    Modifier(
        "dynamics_repeat_request",
        ModifierCategory.DYNAMICS,
        "Repeat Request",
        "User asks agent to repeat something",
        "User says 'sorry, what was that?' or 'can you say that again?', "
        "may have missed something."
    ),
    Modifier(
        "dynamics_hold",
        ModifierCategory.DYNAMICS,
        "Put on Hold",
        "Agent puts user on hold",
        "Agent says 'let me put you on a brief hold', "
        "returns with information or update."
    ),
    Modifier(
        "dynamics_transfer",
        ModifierCategory.DYNAMICS,
        "Transfer to Another Agent",
        "Call needs to be transferred",
        "Agent explains they need to transfer, "
        "may need to re-verify information after transfer."
    ),
    Modifier(
        "dynamics_verification",
        ModifierCategory.DYNAMICS,
        "Identity Verification",
        "Agent needs to verify user's identity",
        "Agent asks security questions, confirms personal details, "
        "may ask for account PIN or last 4 of SSN."
    ),
    Modifier(
        "dynamics_callback_offer",
        ModifierCategory.DYNAMICS,
        "Callback Offered",
        "Agent offers to call back",
        "Agent offers callback instead of hold, "
        "or to call back once issue is resolved."
    ),
    Modifier(
        "dynamics_email_followup",
        ModifierCategory.DYNAMICS,
        "Email Follow-Up",
        "Agent will send email confirmation",
        "Agent offers to send details via email, "
        "confirms email address for follow-up."
    ),
    Modifier(
        "dynamics_system_issue",
        ModifierCategory.DYNAMICS,
        "System Issues",
        "Agent having system or computer issues",
        "Agent mentions system is slow, needs to wait for screen, "
        "apologizes for technical difficulties."
    ),
    Modifier(
        "dynamics_lookup",
        ModifierCategory.DYNAMICS,
        "Account Lookup",
        "Agent looking up account information",
        "Agent asks user to wait while looking up account, "
        "confirms details found in system."
    ),
    Modifier(
        "dynamics_confirmation",
        ModifierCategory.DYNAMICS,
        "Read-Back Confirmation",
        "Agent reads back information for confirmation",
        "Agent repeats phone number, address, or order details "
        "to confirm they have it right."
    ),
    Modifier(
        "dynamics_multi_issue",
        ModifierCategory.DYNAMICS,
        "Multiple Issues",
        "User has more than one issue to resolve",
        "User says 'I also wanted to ask about...' "
        "or has a list of things to address."
    ),
    Modifier(
        "dynamics_follow_up_question",
        ModifierCategory.DYNAMICS,
        "Follow-Up Questions",
        "User has follow-up questions",
        "After main issue resolved, user asks related questions, "
        "wants more information."
    ),
    Modifier(
        "dynamics_misunderstanding",
        ModifierCategory.DYNAMICS,
        "Misunderstanding",
        "There's a miscommunication to resolve",
        "Agent or user misunderstands something, "
        "needs to be clarified and corrected."
    ),
    Modifier(
        "dynamics_long_pause",
        ModifierCategory.DYNAMICS,
        "Long Pauses",
        "Conversation has natural pauses",
        "User pauses to think or find information, "
        "agent waits patiently or prompts."
    ),
    Modifier(
        "dynamics_gratitude_loop",
        ModifierCategory.DYNAMICS,
        "Gratitude Exchange",
        "Extended thank-yous and closing",
        "Longer closing with multiple thanks from both sides, "
        "warm ending to call."
    ),
]

# =============================================================================
# TECHNICAL FACTORS (~25 modifiers)
# =============================================================================

TECHNICAL_MODIFIERS = [
    Modifier(
        "tech_background_noise",
        ModifierCategory.TECHNICAL,
        "Background Noise",
        "There's audible background noise",
        "Conversation includes transcription artifacts from noise, "
        "may need to repeat things, references to noise."
    ),
    Modifier(
        "tech_poor_connection",
        ModifierCategory.TECHNICAL,
        "Poor Connection",
        "Phone connection is poor quality",
        "Words may cut out, agent asks 'are you still there?', "
        "may need to call back."
    ),
    Modifier(
        "tech_spelling_out",
        ModifierCategory.TECHNICAL,
        "Spelling Out Words",
        "User spells out words letter by letter",
        "User spells name, email, or other info: 'S-M-I-T-H', "
        "agent may ask for spelling."
    ),
    Modifier(
        "tech_phonetic",
        ModifierCategory.TECHNICAL,
        "Phonetic Alphabet",
        "User uses phonetic alphabet",
        "User says 'S as in Sam, M as in Mary' or uses NATO phonetic, "
        "common for spelling names or codes."
    ),
    Modifier(
        "tech_digit_by_digit",
        ModifierCategory.TECHNICAL,
        "Digit by Digit",
        "Numbers read one digit at a time",
        "User says 'four one five, five five five, one two three four' "
        "for phone numbers or account numbers."
    ),
    Modifier(
        "tech_slow_speech",
        ModifierCategory.TECHNICAL,
        "Slow/Deliberate Speech",
        "User speaks slowly and deliberately",
        "User enunciates clearly, pauses between words, "
        "may be for clarity or accent."
    ),
    Modifier(
        "tech_fast_speech",
        ModifierCategory.TECHNICAL,
        "Fast Speech",
        "User speaks quickly",
        "User rattles off information quickly, "
        "agent may need to ask to slow down."
    ),
    Modifier(
        "tech_accent",
        ModifierCategory.TECHNICAL,
        "Regional Accent",
        "User has notable regional accent",
        "Transcription may reflect accent, "
        "some words may be pronounced differently."
    ),
    Modifier(
        "tech_speaker_phone",
        ModifierCategory.TECHNICAL,
        "Speaker Phone",
        "User is on speaker phone",
        "Echo effect mentioned, may be harder to hear, "
        "user mentions they're on speaker."
    ),
    Modifier(
        "tech_car_call",
        ModifierCategory.TECHNICAL,
        "Calling from Car",
        "User is calling while driving",
        "Car noise in background, user may be distracted, "
        "uses hands-free, may have connection issues in tunnels."
    ),
    Modifier(
        "tech_multiple_speakers",
        ModifierCategory.TECHNICAL,
        "Multiple People",
        "Multiple people on user's end",
        "User consults with spouse/colleague, "
        "another voice may be heard, pass-along information."
    ),
    Modifier(
        "tech_voice_unclear",
        ModifierCategory.TECHNICAL,
        "Unclear Speech",
        "Some words are hard to understand",
        "Transcription may have [unclear] or mishearings, "
        "agent asks for clarification."
    ),
    Modifier(
        "tech_reading_from_doc",
        ModifierCategory.TECHNICAL,
        "Reading from Document",
        "User is reading information from a document",
        "User pauses while finding info, reads word-for-word, "
        "may stumble over unfamiliar terms."
    ),
    Modifier(
        "tech_looking_up",
        ModifierCategory.TECHNICAL,
        "Looking Up Information",
        "User needs to find information",
        "User asks to hold on while they get card/document, "
        "pauses while searching."
    ),
    Modifier(
        "tech_abbreviations",
        ModifierCategory.TECHNICAL,
        "Uses Abbreviations",
        "User uses common abbreviations",
        "User says 'SSN' instead of social security number, "
        "'DOB' for date of birth, etc."
    ),
    Modifier(
        "tech_number_words",
        ModifierCategory.TECHNICAL,
        "Numbers as Words",
        "Numbers spoken as words",
        "User says 'one two three' instead of 'one twenty-three', "
        "or 'fifteen hundred' vs 'one thousand five hundred'."
    ),
    Modifier(
        "tech_confirmation_style",
        ModifierCategory.TECHNICAL,
        "Confirmation Style",
        "Specific confirmation patterns",
        "User confirms with 'correct', 'that's right', 'yes exactly', "
        "'no, it's actually...'"
    ),
    Modifier(
        "tech_partial_info",
        ModifierCategory.TECHNICAL,
        "Partial Information",
        "Information provided in chunks",
        "User gives partial number, pauses, continues, "
        "or provides info across multiple turns."
    ),
    Modifier(
        "tech_third_party",
        ModifierCategory.TECHNICAL,
        "Third-Party Caller",
        "User calling on behalf of someone else",
        "User is spouse, child, or authorized person, "
        "may need to verify relationship."
    ),
    Modifier(
        "tech_callback_number",
        ModifierCategory.TECHNICAL,
        "Different Callback Number",
        "User provides different callback number",
        "User's calling number differs from account, "
        "provides alternate contact number."
    ),
]

# =============================================================================
# Combine all modifiers
# =============================================================================

ALL_MODIFIERS: list[Modifier] = (
    USER_STATE_MODIFIERS
    + AGENT_BEHAVIOR_MODIFIERS
    + DYNAMICS_MODIFIERS
    + TECHNICAL_MODIFIERS
)

# Index by category
MODIFIERS_BY_CATEGORY: dict[ModifierCategory, list[Modifier]] = {}
for modifier in ALL_MODIFIERS:
    if modifier.category not in MODIFIERS_BY_CATEGORY:
        MODIFIERS_BY_CATEGORY[modifier.category] = []
    MODIFIERS_BY_CATEGORY[modifier.category].append(modifier)


def get_random_modifier(category: ModifierCategory | None = None) -> Modifier:
    """Get a random modifier, optionally filtered by category."""
    if category:
        return random.choice(MODIFIERS_BY_CATEGORY[category])
    return random.choice(ALL_MODIFIERS)


def get_random_modifiers(count: int = 1, mix_categories: bool = True) -> list[Modifier]:
    """
    Get multiple random modifiers.

    Args:
        count: Number of modifiers to return (1-4 recommended)
        mix_categories: If True, try to get modifiers from different categories

    Returns:
        List of modifiers
    """
    if count <= 0:
        return []

    if not mix_categories:
        return random.sample(ALL_MODIFIERS, min(count, len(ALL_MODIFIERS)))

    # Try to get one from each category first
    modifiers = []
    categories = list(ModifierCategory)
    random.shuffle(categories)

    for cat in categories[:count]:
        modifiers.append(get_random_modifier(cat))

    return modifiers


def get_compatible_modifiers(base_modifier: Modifier, count: int = 1) -> list[Modifier]:
    """
    Get modifiers that are compatible with a base modifier.

    Some modifiers conflict (e.g., frustrated + grateful), so we filter those.
    """
    # Define incompatible pairs
    incompatible = {
        "user_frustrated": ["user_grateful", "user_friendly"],
        "user_angry": ["user_grateful", "user_friendly", "user_apologetic"],
        "user_grateful": ["user_frustrated", "user_angry", "user_skeptical"],
        "user_hurried": ["dynamics_small_talk", "dynamics_tangent"],
        "agent_concise": ["agent_thorough", "dynamics_small_talk"],
        "agent_thorough": ["agent_concise", "agent_efficient"],
        "tech_poor_connection": ["dynamics_small_talk"],
    }

    excluded = set(incompatible.get(base_modifier.id, []))
    excluded.add(base_modifier.id)  # Don't include the base modifier

    available = [m for m in ALL_MODIFIERS if m.id not in excluded]
    return random.sample(available, min(count, len(available)))


if __name__ == "__main__":
    # Print stats
    print(f"Total modifiers: {len(ALL_MODIFIERS)}")
    print("\nModifiers by category:")
    for cat, mods in MODIFIERS_BY_CATEGORY.items():
        print(f"  {cat.value}: {len(mods)}")

    print("\nSample modifiers:")
    for mod in get_random_modifiers(4, mix_categories=True):
        print(f"  - {mod.name}: {mod.description}")
