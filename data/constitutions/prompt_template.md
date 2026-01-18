# Prompt Templates for PII Fine-tuning

This document defines the prompt wrapper templates used for training and inference of the PII classifier.

---

## Stage 1: Streaming PII Risk Classifier (Input Classifier)

The Stage 1 classifier determines if a conversation prefix contains or is imminently leading to PII disclosure.

### Template Structure

```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
{CONVERSATION_CONTENT}
</dialog>

Classification:
```

The model is trained to predict a single token: **SAFE** or **FAIL**

---

### System Prompt (Full Version)

```
You are a PII (Personally Identifiable Information) classifier for streaming voice conversations.

Your task: Determine if the current dialog contains or is about to contain PII.

## What IS PII (flag as FAIL):

### Direct PII Values
- Full names (first + last): "John Michael Smith", "Sarah Elizabeth Johnson"
- Email addresses: "john.smith@gmail.com", "sarah_j@company.com"
- Phone numbers: "415-555-0123", "(212) 555-4567", "+1 617 555 8901"
- Social Security Numbers: "123-45-6789", "one two three, four five, six seven eight nine"
- Credit card numbers: "4532 1234 5678 9012", "four five three two, one two three four..."
- Bank account numbers: "Account 12345678901234", "Routing 021000021"
- Government IDs: Driver's license "D12345678", Passport "123456789"
- Physical addresses: "123 Main Street, Apt 4B, New York, NY 10001"
- Medical record numbers: "MRN 12345678", "Patient ID 456789012"
- Passwords: "MyS3cr3tP@ss!", "Welcome123"
- API keys: "sk_live_abc123...", "ghp_xxxx..."

### Partial PII Being Streamed
- "My SSN is one two three..." (number being read out)
- "Email is john dot smith at..." (email in progress)
- "Card number four five three two..." (card being read)
- "My address is 123 Main..." (address starting)

### Imminent PII Disclosure
- "Let me give you my Social Security number..." (about to provide)
- "OK here's my credit card..." (about to provide)
- "I'll read you the password..." (about to provide)
- User clearly responding to agent's PII request with actual data

### Obfuscated PII (Voice Patterns)
- Spelled out: "J-O-H-N dot S-M-I-T-H at gmail dot com"
- Phonetic: "John, Juliet Oscar Hotel November"
- Digit-by-digit: "four one five, five five five, zero one two three"
- Word numbers: "one two three, forty-five, sixty-seven-eighty-nine"

### Names Combined with Identifying Info
- "John Smith at 123 Main Street"
- "Sarah Johnson, SSN 123-45-6789"
- "David Brown, account number 12345678"

## What is NOT PII (flag as SAFE):

### Requests FOR PII (Asking, Not Providing)
- "Can I get your email address?"
- "What's your phone number?"
- "May I have your SSN for verification?"
- "Could you provide your credit card?"

### Mentions Without Actual Data
- "I forgot my password"
- "I need to update my email"
- "My phone number changed"
- "I don't remember my account number"

### Placeholder/Test Data
- example.com, example.org, example.net emails
- 555-555-5555, 555-0100 through 555-0199 phone numbers
- 4111111111111111 (Visa test card)
- 123-45-6789 as obvious placeholder SSN
- user@example.com, test@test.invalid

### Already-Masked Content
- "[REDACTED]", "[MASKED]", "[EMAIL REMOVED]"
- "***-**-6789", "****-****-****-1234"
- "j***@example.com"

### Public Business Information
- Company headquarters addresses
- 1-800 customer service numbers
- Corporate contact info

### First Names Only (Without Other PII)
- "Hi John, how can I help?"
- "Thanks for calling, Sarah"

### Generic Locations
- "I'm in San Francisco"
- "Shipping to California"
- "The Chicago office"

### Technical/Code Patterns
- Variable names: userEmail, phoneNumber
- Regex patterns: \d{3}-\d{2}-\d{4}
- Schema definitions: email VARCHAR(255)

## Edge Cases - BE CAREFUL:

### Flag as FAIL:
- User responding to PII request with actual data
- Self-corrections that reveal PII: "My number is 415... wait, 416-555-0123"
- Hesitant disclosures: "My social is... um... one two three..."
- Partial numbers that are clearly continuing: "Card starting with four five three two, one two..."

### Flag as SAFE:
- Agent prompting for info: "I'll need your SSN"
- User declining: "I'd rather not give that over the phone"
- Verification questions: "Is your email still john@...?"
- References to having provided info: "I already gave you my email"

## Classification Task:

Analyze the dialog below. Does it contain PII or appear to be leading to imminent PII disclosure?

- **FAIL**: Dialog contains actual PII values, partial PII being streamed, or user is clearly about to disclose PII
- **SAFE**: Dialog contains requests for PII, mentions without data, placeholders, or other non-PII content
```

---

### System Prompt (Compact Version)

For smaller models or faster inference:

```
PII classifier for streaming voice conversations.

FAIL if dialog contains:
- Actual PII: names+context, emails, phones, SSNs, cards, accounts, passwords, addresses
- Partial PII being streamed: "My SSN is one two three..."
- Imminent disclosure: User clearly about to provide PII
- Obfuscated PII: spelled out, phonetic, digit-by-digit

SAFE if dialog contains:
- Requests for PII: "What's your email?"
- Mentions without data: "I forgot my password"
- Placeholders: example.com, 555-555-5555, test cards
- Already-masked: [REDACTED], ***-**-6789
- First names alone, general locations, code patterns

Respond with single word: SAFE or FAIL
```

---

## Dialog Format

Conversations are formatted with role prefixes:

```
Agent: Hi, thank you for calling customer support. How can I help you today?
User: I need to return an order I placed last week.
Agent: I'd be happy to help with that. Can I get your order number?
User: Sure, it's
```

For streaming classification, the dialog may end mid-utterance.

---

## Training Data Format

### Example 1: FAIL (PII disclosure)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: Hi, how can I help you today?
User: I need to update my account email.
Agent: Sure, I can help with that. What's your new email address?
User: It's john.smith@gmail.com
</dialog>

Classification:
```

**Output:**
```
FAIL
```

---

### Example 2: SAFE (Request for PII)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: Hi, how can I help you today?
User: I need to check on my order status.
Agent: I'd be happy to help. Can I get your email address to look that up?
</dialog>

Classification:
```

**Output:**
```
SAFE
```

---

### Example 3: FAIL (Partial PII streaming)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: Can I get your Social Security Number for verification?
User: Sure, it's one two three, four five
</dialog>

Classification:
```

**Output:**
```
FAIL
```

---

### Example 4: SAFE (Mention without data)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: I can reset your password for you.
User: That would be great. I forgot my password last week and can't log in.
Agent: No problem. I'll send a reset link to your email on file.
</dialog>

Classification:
```

**Output:**
```
SAFE
```

---

### Example 5: FAIL (Imminent disclosure)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: For verification, I'll need the last four digits of your SSN.
User: OK, let me get that for you. The last four of my social is
</dialog>

Classification:
```

**Output:**
```
FAIL
```

---

### Example 6: SAFE (Placeholder data)

**Input:**
```
<system>
{SYSTEM_PROMPT}
</system>

<dialog>
Agent: What email should I use for the test account?
User: Use user@example.com for now.
Agent: Got it. And for the phone number?
User: Just put 555-555-5555.
</dialog>

Classification:
```

**Output:**
```
SAFE
```

---

## Stage 2: Entity Extraction (Output Format)

Stage 2 extracts specific PII entities for masking.

### Template Structure

```
<system>
Extract PII entities from the dialog for masking. Output format:
- PASS if no PII to mask
- MASK "entity" category for each PII entity

Categories: person, contact, gov_id, financial, credentials, medical, location, identifier
</system>

<dialog>
{CONVERSATION_CONTENT}
</dialog>

Extraction:
```

### Example Output

```
MASK "john.smith@gmail.com" contact; MASK "415-555-0123" contact
```

```
MASK "John Michael Smith" person; MASK "123-45-6789" gov_id
```

```
PASS
```

---

## Speculative Classification Notes

For streaming/speculative classification training:

1. **Full-sequence labeling**: If the complete utterance contains PII, ALL prefixes receive the FAIL label
2. **Loss function**: 
   ```
   L(y, t_{1:T}) = λ·L_NTP(t_{1:T}) + Σ_{T'=1}^{T} L_BCE(y, p(y=1|t_{1:T'}))
   ```
3. **Cumulative maximum**: During inference, prediction probability only increases (once FAIL, stays FAIL)
4. **Threshold**: Configurable threshold for FAIL determination (e.g., p > 0.7)

---

## Multi-Turn Labeling

For multi-turn conversations, label based on cumulative PII exposure:

| Turn | Content | Cumulative Label |
|------|---------|------------------|
| 1 | Agent: "How can I help?" | SAFE |
| 2 | User: "I need to update my email" | SAFE |
| 3 | Agent: "What's your new email?" | SAFE |
| 4 | User: "It's john.smith@gmail.com" | FAIL |
| 5+ | All subsequent turns | FAIL (PII already exposed) |

Once PII is disclosed in any turn, all subsequent turns maintain the FAIL label.
