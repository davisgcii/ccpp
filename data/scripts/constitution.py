"""
Constitution loader for PII detection training.

Parses the markdown constitution files into structured data:
- pii_harmful.md: Examples that SHOULD trigger detection (FAIL)
- pii_harmless.md: Examples that should NOT trigger detection (SAFE)
- prompt_template.md: Prompt templates for classifier

Provides structured access to examples by category for:
- Training data generation
- Test case creation
- Prompt construction
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict
import re


class PIICategory(str, Enum):
    """PII categories matching the constitution."""
    PERSON = "person"
    CONTACT = "contact"
    GOV_ID = "gov_id"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"
    MEDICAL = "medical"
    LOCATION = "location"
    IDENTIFIER = "identifier"


class SafeCategory(str, Enum):
    """Categories for SAFE (non-PII) examples."""
    REQUESTS_FOR_PII = "requests_for_pii"
    MENTIONS_WITHOUT_DATA = "mentions_without_data"
    PLACEHOLDER_TEST = "placeholder_test"
    PARTIAL_MASKED = "partial_masked"
    PUBLIC_BUSINESS = "public_business"
    TECHNICAL_NONPERSONAL = "technical_nonpersonal"
    EDUCATIONAL = "educational"
    VAGUE_INFO = "vague_info"
    ALREADY_MASKED = "already_masked"
    VOICE_PATTERNS = "voice_patterns"


@dataclass
class Example:
    """A single example from the constitution."""
    text: str
    subcategory: str  # e.g., "Full names (first + last)"
    notes: str = ""   # Any additional context

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "subcategory": self.subcategory,
            "notes": self.notes,
        }


@dataclass
class ConstitutionCategory:
    """A category with its examples."""
    id: str
    name: str
    description: str
    examples: List[Example] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "examples": [e.to_dict() for e in self.examples],
        }


@dataclass
class Constitution:
    """Full constitution with harmful and harmless categories."""
    harmful_categories: Dict[str, ConstitutionCategory] = field(default_factory=dict)
    harmless_categories: Dict[str, ConstitutionCategory] = field(default_factory=dict)
    classifier_prompt: str = ""
    classifier_prompt_compact: str = ""
    stage2_prompt: str = ""

    def get_harmful_examples(self, category: PIICategory) -> List[Example]:
        """Get all harmful examples for a PII category."""
        cat = self.harmful_categories.get(category.value)
        return cat.examples if cat else []

    def get_harmless_examples(self, category: SafeCategory | None = None) -> List[Example]:
        """Get harmless examples, optionally filtered by category."""
        if category:
            cat = self.harmless_categories.get(category.value)
            return cat.examples if cat else []
        # Return all harmless examples
        all_examples = []
        for cat in self.harmless_categories.values():
            all_examples.extend(cat.examples)
        return all_examples

    def all_harmful_examples(self) -> List[Example]:
        """Get all harmful examples across all categories."""
        all_examples = []
        for cat in self.harmful_categories.values():
            all_examples.extend(cat.examples)
        return all_examples


def _parse_harmful_constitution(content: str) -> Dict[str, ConstitutionCategory]:
    """Parse the harmful (PII) constitution markdown."""
    categories = {}
    current_category = None
    current_subcategory = None

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Match category header: ## Category: person
        cat_match = re.match(r'^## Category:\s*(\w+)', line)
        if cat_match:
            cat_id = cat_match.group(1).lower()
            # Get description from next non-empty line
            desc = ""
            j = i + 1
            while j < len(lines) and lines[j].strip():
                if lines[j].strip().startswith('**') and not lines[j].strip().startswith('### '):
                    # This is the description line
                    desc = lines[j].strip().strip('*')
                    break
                j += 1

            current_category = ConstitutionCategory(
                id=cat_id,
                name=cat_id.replace('_', ' ').title(),
                description=desc,
            )
            categories[cat_id] = current_category
            i += 1
            continue

        # Match subcategory header: **Full names (first + last)**
        if current_category and line.startswith('**') and line.endswith('**'):
            # Skip section headers like "### Must flag (FAIL):"
            if 'Must flag' not in line and 'MUST flag' not in line:
                current_subcategory = line.strip('*').strip()

        # Match example: - "example text"
        if current_category and current_subcategory:
            example_match = re.match(r'^-\s+"(.+)"', line)
            if example_match:
                example_text = example_match.group(1)
                current_category.examples.append(Example(
                    text=example_text,
                    subcategory=current_subcategory,
                ))
            # Also match examples without quotes
            elif line.startswith('- ') and not line.startswith('- **'):
                example_text = line[2:].strip()
                if example_text and not example_text.startswith('('):
                    current_category.examples.append(Example(
                        text=example_text,
                        subcategory=current_subcategory,
                    ))

        i += 1

    return categories


def _parse_harmless_constitution(content: str) -> Dict[str, ConstitutionCategory]:
    """Parse the harmless (SAFE) constitution markdown."""
    categories = {}
    current_category = None
    current_subcategory = None

    # Map section numbers to category IDs
    section_to_category = {
        "1": SafeCategory.REQUESTS_FOR_PII.value,
        "2": SafeCategory.MENTIONS_WITHOUT_DATA.value,
        "3": SafeCategory.PLACEHOLDER_TEST.value,
        "4": SafeCategory.PARTIAL_MASKED.value,
        "5": SafeCategory.PUBLIC_BUSINESS.value,
        "6": SafeCategory.TECHNICAL_NONPERSONAL.value,
        "7": SafeCategory.EDUCATIONAL.value,
        "8": SafeCategory.VAGUE_INFO.value,
        "9": SafeCategory.ALREADY_MASKED.value,
        "10": SafeCategory.VOICE_PATTERNS.value,
    }

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Match section header: ## 1. Requests FOR PII
        section_match = re.match(r'^## (\d+)\.\s+(.+)', line)
        if section_match:
            section_num = section_match.group(1)
            section_name = section_match.group(2)
            cat_id = section_to_category.get(section_num, f"section_{section_num}")

            # Get description from following lines
            desc = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('#') and not next_line.startswith('-'):
                    desc = next_line
                    break
                if next_line.startswith('#'):
                    break
                j += 1

            current_category = ConstitutionCategory(
                id=cat_id,
                name=section_name,
                description=desc,
            )
            categories[cat_id] = current_category
            current_subcategory = None
            i += 1
            continue

        # Match subsection header (for voice patterns and other detailed sections)
        subsection_match = re.match(r'^### (\d+\.\d+)\s+(.+)', line)
        if subsection_match:
            current_subcategory = subsection_match.group(2)
            i += 1
            continue

        # Match subcategory header: **Agent requests for information**
        if current_category and line.startswith('**') and line.endswith('**'):
            if 'Must NOT flag' not in line and 'SAFE' not in line:
                current_subcategory = line.strip('*').strip()

        # Match example: - "example text"
        if current_category:
            subcat = current_subcategory or "General"
            example_match = re.match(r'^-\s+"(.+)"', line)
            if example_match:
                example_text = example_match.group(1)
                current_category.examples.append(Example(
                    text=example_text,
                    subcategory=subcat,
                ))
            # Also match examples without quotes
            elif line.startswith('- ') and not line.startswith('- **'):
                example_text = line[2:].strip()
                if example_text and not example_text.startswith('('):
                    current_category.examples.append(Example(
                        text=example_text,
                        subcategory=subcat,
                    ))

        i += 1

    return categories


def _parse_prompt_template(content: str) -> tuple[str, str, str]:
    """Parse prompt templates from markdown, returning (full, compact, stage2)."""
    # Find the full system prompt
    full_prompt = ""
    compact_prompt = ""
    stage2_prompt = ""

    # Look for specific sections
    sections = content.split('## ')

    for section in sections:
        if 'System Prompt (Full Version)' in section or 'Stage 1' in section:
            match = re.search(r'```\n(.*?)```', section, re.DOTALL)
            if match:
                full_prompt = match.group(1).strip()
        elif 'System Prompt (Compact Version)' in section:
            match = re.search(r'```\n(.*?)```', section, re.DOTALL)
            if match:
                compact_prompt = match.group(1).strip()
        elif 'Stage 2' in section:
            match = re.search(r'```\n(.*?)```', section, re.DOTALL)
            if match:
                stage2_prompt = match.group(1).strip()

    return full_prompt, compact_prompt, stage2_prompt


def load_constitution(
    constitutions_dir: Path | str | None = None
) -> Constitution:
    """
    Load and parse the constitution files.

    Args:
        constitutions_dir: Path to data/constitutions/ directory.
            If None, uses default path relative to this file.

    Returns:
        Constitution object with parsed categories and prompts.
    """
    if constitutions_dir is None:
        # Default: look for constitutions in data/constitutions/
        this_file = Path(__file__)
        data_dir = this_file.parent.parent  # data/scripts -> data
        constitutions_dir = data_dir / "constitutions"

    constitutions_dir = Path(constitutions_dir)

    constitution = Constitution()

    # Load harmful constitution
    harmful_path = constitutions_dir / "pii_harmful.md"
    if harmful_path.exists():
        with open(harmful_path, 'r') as f:
            content = f.read()
        constitution.harmful_categories = _parse_harmful_constitution(content)

    # Load harmless constitution
    harmless_path = constitutions_dir / "pii_harmless.md"
    if harmless_path.exists():
        with open(harmless_path, 'r') as f:
            content = f.read()
        constitution.harmless_categories = _parse_harmless_constitution(content)

    # Load prompt templates
    prompt_path = constitutions_dir / "prompt_template.md"
    if prompt_path.exists():
        with open(prompt_path, 'r') as f:
            content = f.read()
        full, compact, stage2 = _parse_prompt_template(content)
        constitution.classifier_prompt = full
        constitution.classifier_prompt_compact = compact
        constitution.stage2_prompt = stage2

    return constitution


def get_pii_category_description(category: PIICategory) -> str:
    """Get human-readable description for a PII category."""
    descriptions = {
        PIICategory.PERSON: "Personal identity - full names, usernames tied to real identity",
        PIICategory.CONTACT: "Contact information - email addresses, phone numbers, mailing addresses",
        PIICategory.GOV_ID: "Government IDs - SSN, passport, driver's license, tax IDs",
        PIICategory.FINANCIAL: "Financial - credit cards, bank accounts, routing numbers",
        PIICategory.CREDENTIALS: "Credentials - passwords, API keys, tokens, private keys",
        PIICategory.MEDICAL: "Medical - diagnoses, prescriptions, medical record numbers",
        PIICategory.LOCATION: "Location - precise addresses, GPS coordinates",
        PIICategory.IDENTIFIER: "Identifiers - order numbers, account IDs, tracking numbers",
    }
    return descriptions.get(category, category.value)


def get_redaction_placeholder(category: PIICategory) -> str:
    """Get the redaction placeholder for a category."""
    placeholders = {
        PIICategory.PERSON: "[PERSON]",
        PIICategory.CONTACT: "[CONTACT]",
        PIICategory.GOV_ID: "[GOV_ID]",
        PIICategory.FINANCIAL: "[FINANCIAL]",
        PIICategory.CREDENTIALS: "[CREDENTIALS]",
        PIICategory.MEDICAL: "[MEDICAL]",
        PIICategory.LOCATION: "[LOCATION]",
        PIICategory.IDENTIFIER: "[IDENTIFIER]",
    }
    return placeholders.get(category, "[REDACTED]")


# Mapping from detailed category to redaction placeholder
CATEGORY_PLACEHOLDERS = {
    # Person subcategories
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "address": "[ADDRESS]",
    "name": "[PERSON]",
    "ssn": "[SSN]",
    "credit_card": "[CREDIT_CARD]",
    "bank_account": "[BANK_ACCOUNT]",
    "password": "[PASSWORD]",
    "api_key": "[API_KEY]",
    "order_id": "[ORDER_ID]",
    "account_id": "[ACCOUNT_ID]",
    "tracking": "[TRACKING_NUMBER]",
    "medical_record": "[MRN]",
    "prescription": "[PRESCRIPTION]",
    "diagnosis": "[DIAGNOSIS]",
    "drivers_license": "[DL_NUMBER]",
    "passport": "[PASSPORT]",
    "dob": "[DOB]",
    "date_of_birth": "[DOB]",
}


if __name__ == "__main__":
    # Test loading the constitution
    constitution = load_constitution()

    print("=== HARMFUL CATEGORIES ===")
    print(f"Total harmful categories: {len(constitution.harmful_categories)}")
    for cat_id, cat in constitution.harmful_categories.items():
        print(f"\n{cat_id}: {len(cat.examples)} examples")
        # Show first 3 examples
        for ex in cat.examples[:3]:
            print(f"  - [{ex.subcategory}] {ex.text[:60]}...")

    print("\n=== HARMLESS CATEGORIES ===")
    print(f"Total harmless categories: {len(constitution.harmless_categories)}")
    for cat_id, cat in constitution.harmless_categories.items():
        print(f"\n{cat_id}: {len(cat.examples)} examples")
        # Show first 3 examples
        for ex in cat.examples[:3]:
            print(f"  - [{ex.subcategory}] {ex.text[:60]}...")

    print("\n=== PROMPTS ===")
    print(f"Full prompt length: {len(constitution.classifier_prompt)} chars")
    print(f"Compact prompt length: {len(constitution.classifier_prompt_compact)} chars")
    print(f"Stage 2 prompt length: {len(constitution.stage2_prompt)} chars")

    # Stats
    total_harmful = sum(len(c.examples) for c in constitution.harmful_categories.values())
    total_harmless = sum(len(c.examples) for c in constitution.harmless_categories.values())
    print(f"\nTotal examples: {total_harmful} harmful, {total_harmless} harmless")
