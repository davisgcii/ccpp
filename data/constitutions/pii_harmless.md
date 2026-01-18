# PII Constitution - Harmless (SAFE)

This constitution defines content that **should NOT trigger PII detection** (label: SAFE).

Adding a detailed harmless constitution is essential for limiting over-refusals and training classifiers to distinguish true PII from benign content that superficially resembles PII.

---

## 1. Requests FOR PII (Not Providing PII)

Content where someone is **asking for** PII, not providing it.

### Must NOT flag (SAFE):

**Agent requests for information**
- "Can I get your email address?"
- "What's your phone number?"
- "May I have your Social Security number for verification?"
- "Could you provide your credit card number?"
- "What address should we ship to?"
- "Can you spell your last name for me?"
- "What's your date of birth?"
- "I'll need your account number"
- "Please provide your order number"
- "What's your member ID?"

**Verification prompts**
- "For security, I need the last four of your SSN"
- "Can you confirm your billing address?"
- "What's the CVV on the back of your card?"
- "I'll need to verify your identity"
- "Please confirm your email address"
- "What's the phone number on file?"

**Form/field descriptions**
- "Enter your email in the first field"
- "The next box is for your phone number"
- "You'll need to provide your SSN"
- "This form requires your full address"
- "Type your password in the password field"

**Instructions about PII**
- "You'll need to have your account number ready"
- "Make sure you have your credit card handy"
- "I'll ask you for some personal information"
- "We require government ID for this transaction"
- "You should have your insurance card available"

---

## 2. Mentions Without Actual Data

References to PII categories without revealing actual values.

### Must NOT flag (SAFE):

**Vague references to PII**
- "I forgot my password"
- "I don't remember my account number"
- "I lost my credit card"
- "I need to update my email"
- "My phone number changed"
- "I moved to a new address"
- "I need a new SSN card"
- "My driver's license expired"

**Discussions about PII types**
- "I'm worried about my SSN being compromised"
- "Is it safe to give my credit card over the phone?"
- "Should I share my email with them?"
- "I don't want to give out my address"
- "My password might have been hacked"
- "Someone may have stolen my identity"

**Past tense without values**
- "I gave them my SSN yesterday"
- "I already provided my credit card"
- "I sent you my email address earlier"
- "I updated my phone number last week"
- "I entered my password but it didn't work"

**Questions about PII (without providing)**
- "Do you have my email on file?"
- "Is my phone number in your system?"
- "Did you receive my account information?"
- "Can you see my address?"
- "Do you have my order number?"

---

## 3. Placeholder and Test Data

Standard placeholders, test values, and example data.

### Must NOT flag (SAFE):

**Placeholder email domains (RFC 2606/6761)**
- "user@example.com"
- "admin@example.org"
- "test@example.net"
- "john.doe@example.com"
- "support@test.example.com"
- "noreply@example.org"
- "anything@localhost"
- "email@invalid"

**Placeholder phone numbers**
- "555-0100" through "555-0199" (US reserved fictional)
- "555-555-5555"
- "(555) 555-5555"
- "1-800-555-5555"
- "123-456-7890" (obvious placeholder)
- "000-000-0000"
- "999-999-9999"
- "+1-555-555-5555"

**Test credit card numbers (official)**
- "4111111111111111" (Visa test)
- "5500000000000004" (Mastercard test)
- "378282246310005" (Amex test)
- "6011111111111117" (Discover test)
- "Any card from Stripe test mode"
- "PayPal sandbox cards"

**Placeholder SSN patterns**
- "123-45-6789" (obvious placeholder)
- "000-00-0000"
- "999-99-9999"
- "XXX-XX-XXXX"
- "NNN-NN-NNNN"
- "SSNs with 00 in middle group" (invalid)
- "SSNs starting with 9XX" (ITINs, contextual)

**Test API keys (documented)**
- "sk_test_*" (Stripe test mode)
- "pk_test_*" (Stripe test publishable)
- "AKIAIOSFODNN7EXAMPLE" (AWS example)
- "YOUR_API_KEY_HERE"
- "INSERT_TOKEN_HERE"
- "REPLACE_WITH_YOUR_KEY"
- "demo_key_12345"

**Placeholder addresses**
- "123 Main Street, Anytown, USA"
- "456 Test Avenue"
- "123 Example Road"
- "Addresses with ZIP 12345"
- "Addresses with ZIP 00000"
- "Addresses with ZIP 99999"

**Template variables**
- "{{email}}"
- "{{phone_number}}"
- "${SSN}"
- "<EMAIL>"
- "[PHONE]"
- "{customer_name}"
- "___@___.com"

---

## 4. Already-Masked/Redacted Content

Content that has already been masked or redacted.

### Must NOT flag (SAFE):

**Standard mask patterns**
- "[REDACTED]"
- "[MASKED]"
- "[REMOVED]"
- "[EMAIL REMOVED]"
- "[PHONE REDACTED]"
- "[SSN HIDDEN]"
- "[ADDRESS WITHHELD]"

**Partial masks**
- "j***@example.com"
- "***-**-6789" (last 4 SSN only)
- "****-****-****-1234" (last 4 of card)
- "(***) ***-1234"
- "John S***"
- "123 M*** Street"

**Hash/token references**
- "User ID: abc123xyz"
- "Reference: REF_XXXXX"
- "Token: ****"
- "Account: ********1234"
- "Confirmation: XXXXXX"

---

## 5. Public and Business Information

Information that is publicly available or generic business data.

### Must NOT flag (SAFE):

**Public company contact info**
- "Call Apple at 1-800-275-2273"
- "Contact Amazon customer service"
- "Google headquarters is at 1600 Amphitheatre Parkway"
- "Apple Park is at One Apple Park Way"
- "Microsoft is in Redmond, Washington"

**Generic customer service numbers**
- "Call our 1-800 number"
- "Our support line is 1-888-..."
- "Dial our toll-free number"
- "Contact us at our main line"

**Business addresses (public)**
- "Corporate headquarters"
- "Our office is located at..."
- "Visit us at our store location"
- "Retail store address"

**Published contact info**
- "Press contact information"
- "Investor relations email"
- "Media inquiries"
- "Public PR contact"

**Generic roles/titles**
- "Ask for the manager"
- "Speak to customer service"
- "Contact the billing department"
- "Reach out to support"

---

## 6. First Names Only (Without Identifying Context)

Standalone first names without additional identifying information.

### Must NOT flag (SAFE):

**Greetings with first names**
- "Hi John, how can I help?"
- "Thanks for calling, Sarah"
- "Good morning, David"
- "Hello Maria"
- "Welcome back, Mike"

**References to common names**
- "Is this John?"
- "Can I speak to Sarah?"
- "This is for David"
- "Appointment for Maria"
- "Ask for Mike"

**Names without context**
- "John mentioned..."
- "Sarah said..."
- "David called earlier"
- "Maria's preference"
- "Check with Mike"

---

## 7. Generic Locations (Not Precise)

General location references that don't identify specific individuals.

### Must NOT flag (SAFE):

**City/State references**
- "I'm in San Francisco"
- "Shipping to California"
- "Customer in New York"
- "The Texas office"
- "Our Chicago branch"

**Region references**
- "East coast delivery"
- "West coast time"
- "Midwest region"
- "Southern states"
- "New England area"

**Country references**
- "Shipping to Canada"
- "UK customer"
- "European office"
- "Australia warehouse"

**General area**
- "Downtown location"
- "The mall store"
- "Airport branch"
- "University campus"

---

## 8. Numbers That Resemble PII But Aren't

Numeric patterns that look like PII but serve different purposes.

### Must NOT flag (SAFE):

**Product identifiers**
- "SKU: 1234567890"
- "Part number PN-123-456-789"
- "Model: XR-5500-PRO"
- "Item #123456"
- "UPC barcode"
- "ISBN 978-0-12-345678-9"

**Date/time values**
- "January 15, 2024"
- "03/15/2024"
- "2024-01-15"
- "3:45 PM"
- "15:45:00"

**Measurements and quantities**
- "$123.45"
- "45 pounds"
- "100 units"
- "5.5 feet"
- "99.9%"
- "1,234,567 users"

**Technical numbers**
- "Version 3.14.159"
- "Build 20240115"
- "Port 8080"
- "HTTP 404"
- "Error code 12345"

**Reference numbers (generic context)**
- "Page 123"
- "Chapter 5"
- "Section 4.2"
- "Line 1234"
- "Row 567"

**Financial amounts (not account numbers)**
- "Total: $1,234.56"
- "Balance: $500.00"
- "Payment of $99.99"
- "Invoice total"
- "Monthly fee"

**Sequence/batch numbers**
- "Batch #12345"
- "Lot number ABC123"
- "Sequence 001"
- "Run #2024-001"

---

## 9. Educational and Informational Content

Discussions about PII concepts without real data.

### Must NOT flag (SAFE):

**Explaining PII formats**
- "SSNs follow the pattern XXX-XX-XXXX"
- "Credit cards are 13-19 digits"
- "Emails have @ and domain"
- "Phone numbers vary by country"
- "Driver's licenses vary by state"

**Security/privacy education**
- "Never share your password"
- "Protect your SSN"
- "Be careful with credit card info"
- "Use two-factor authentication"
- "Strong passwords should..."

**Compliance discussions**
- "GDPR requires..."
- "HIPAA protects..."
- "PCI compliance means..."
- "Data protection regulations"
- "Privacy policy updates"

**How-to without real data**
- "How to change your password"
- "Steps to update your email"
- "How to report identity theft"
- "Freezing your credit"

---

## 10. Code and Technical Patterns

Technical content that resembles PII patterns.

### Must NOT flag (SAFE):

**Variable names**
- "userEmail"
- "phoneNumber"
- "ssnField"
- "cardNumber"
- "apiKey"

**Function signatures**
- "validateEmail(email)"
- "formatPhone(number)"
- "maskSSN(ssn)"
- "encryptCard(cardNumber)"

**Regex patterns**
- "\d{3}-\d{2}-\d{4}"
- "[a-zA-Z0-9._%+-]+@"
- "^\+?[0-9]{10,15}$"

**Database schema**
- "email VARCHAR(255)"
- "phone_number CHAR(10)"
- "ssn ENCRYPTED"
- "card_token TEXT"

**Config file structures**
- "email_field:"
- "phone_regex:"
- "ssn_validation:"
- "api_key_prefix:"

**Example code**
- "// Enter email here"
- "# Phone number validation"
- "/* SSN format check */"

---

## 11. Voice Conversation Patterns (Not PII)

Common voice patterns that don't contain actual PII.

### Must NOT flag (SAFE):

**Acknowledgments**
- "Got it"
- "I understand"
- "Okay"
- "Sure, one moment"
- "Let me check"

**Clarification requests**
- "Can you repeat that?"
- "I didn't catch that"
- "Could you spell that?"
- "One more time please"
- "Say that again?"

**Procedural language**
- "Let me pull up your account"
- "I'm checking our system"
- "One moment while I verify"
- "I'll need to transfer you"
- "Please hold"

**Filler words and hesitations**
- "Um..."
- "Uh..."
- "Let me see..."
- "Well..."
- "So..."

**Confirmations**
- "Is that correct?"
- "Did I get that right?"
- "Can you confirm?"
- "Does that look right?"

---

## 12. Out-of-Scope Harmful Content

Content that may be harmful but is NOT PII-related.

### Must NOT flag (for PII purposes) (SAFE):

**General complaints**
- "Your service is terrible"
- "I want to cancel"
- "This is unacceptable"
- "I'm very frustrated"

**Threats (without PII)**
- "I'll report you to the BBB"
- "I'm calling my lawyer"
- "I'll leave a bad review"
- "I want to speak to a manager"

**Other sensitive topics (not PII)**
- "I need to file a complaint"
- "There's a billing error"
- "You charged me twice"
- "I never ordered this"

---

## 13. Near-Miss Edge Cases

Content that's very close to PII but technically isn't.

### Must NOT flag (SAFE):

**Partial info without identity**
- "My area code is 415" (just area code)
- "I'm in the 94102 zip code" (just zip)
- "I'm on the third floor" (no building)
- "My birthday is in March" (no day/year)

**Generic usernames**
- "My username is admin"
- "Login as guest"
- "Username: test_user"
- "Account: demo"

**Incomplete that stops being completed**
- "My phone is... actually never mind"
- "My email... wait, let me just verify differently"
- "I was going to give my SSN but... is there another way?"

**Obvious fiction**
- "Santa Claus at the North Pole"
- "John Doe at 123 Fake Street"
- "Jane Doe, SSN 000-00-0000"
- "Test User at test@test.test"

---

## Voice-Specific Safe Patterns

### Must NOT flag (SAFE):

**Spelling without PII**
- "That's S-M-I-T-H" (when not part of full name + other PII)
- "M as in Mary"
- "The letter B"
- "Capital A"

**Numbers in non-PII context**
- "Four items"
- "Three weeks"
- "Five dollars"
- "Two options"
- "About ten minutes"

**Dictation stops**
- "Actually, don't need to write that down"
- "Wait, let me verify another way"
- "Can we use a different method?"

---

## Notes for Synthetic Data Generation

Use this constitution to generate:

1. **Negative examples (SAFE cases)**
   - Agent requests for PII
   - Mentions without data
   - Placeholder/test data
   - Already-masked content

2. **Hard negatives (look like PII but aren't)**
   - example.com emails
   - 555 phone numbers
   - Test credit cards
   - Placeholder SSNs
   - Public business info

3. **Context-dependent safe content**
   - First names alone
   - City/state without address
   - Generic account references
   - Technical/code patterns

4. **Voice-specific negatives**
   - Agent prompts for info
   - Clarification requests
   - Filler words
   - Acknowledgments
   - Procedural language

The classifier must learn to distinguish:
- "What's your email?" → SAFE (request)
- "My email is john@gmail.com" → FAIL (disclosure)
- "user@example.com" → SAFE (placeholder)
- "user@gmail.com" → FAIL (real email)
- "555-555-5555" → SAFE (test number)
- "415-555-0123" → FAIL (real number)
- "I forgot my password" → SAFE (mention)
- "My password is Secret123" → FAIL (disclosure)
