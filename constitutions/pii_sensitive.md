# PII and Sensitive Information Constitution

This constitution defines categories of content that the exchange classifier should detect and mask. The system performs **streaming redaction** - sensitive spans are masked while the rest of the content continues to flow.

We train Constitutional Classifiers to identify inputs and outputs that contain or request information about personal identifiable information (PII) and sensitive data categories defined below.

---

## Category: pii/direct

**Direct personally identifiable information** - data that directly identifies a specific individual without requiring additional context.

### Must mask:

**Email addresses (personal or work)**
- Personal email addresses (john.doe@gmail.com, jane_smith@yahoo.com)
- Work email addresses (jsmith@company.com, john@startup.io)
- Custom domain personal emails (me@johndoe.com)
- Email addresses in contact blocks or signatures
- Email addresses shared in response to "how can I reach you"
- Email addresses extracted from documents or databases
- Email addresses in CSV/JSON data exports

**Phone numbers (all formats)**
- US format: (555) 123-4567, 555-123-4567, 555.123.4567
- International format: +1-555-123-4567, +44 20 7946 0958
- Mobile numbers, landlines, fax numbers
- Phone numbers in vCards or contact information
- Emergency contact numbers for specific individuals
- Phone numbers shared for scheduling or callbacks
- Phone numbers in customer records or logs

**Government identification numbers**
- Social Security Numbers (SSN): 123-45-6789
- Passport numbers: US format, UK format, etc.
- Driver's license numbers by state/country
- National ID numbers (NIE, NIN, Aadhaar, etc.)
- Tax identification numbers (TIN, ITIN)
- Immigration document numbers (visa numbers, green card numbers)
- Military ID numbers
- Voter registration numbers

**Full names combined with identifying context**
- Full name + date of birth
- Full name + address
- Full name + employer
- Full name + medical condition
- Full name + financial information
- Full name + phone/email
- Full name in context that reveals identity (e.g., "John Smith who works at Acme Corp on 5th floor")

**Physical addresses (residential)**
- Street address: 123 Main Street, Apt 4B, New York, NY 10001
- Full mailing addresses with ZIP/postal codes
- Apartment/unit numbers combined with building address
- Home addresses shared for deliveries
- Residential addresses in contact databases
- Return addresses on correspondence
- Home addresses revealed through location history

**Biometric identifiers**
- Fingerprint hashes or templates
- Facial recognition embeddings
- Voice print identifiers
- Retinal/iris scan data
- DNA sequences linked to individuals
- Gait analysis data
- Behavioral biometric signatures

**Online account identifiers tied to real identity**
- Social media handles when linked to real names
- Gaming usernames when identity is revealed
- Forum accounts with identifying information
- Dating profile usernames with real photos/details

---

## Category: pii/indirect

**Indirect/quasi-identifiers** - data that can identify individuals when combined with other data points.

### Must mask when combination is specific enough to identify:

**Employment + location combinations**
- Job title + specific employer + city (e.g., "Senior Engineer at Twitter in SF")
- Department + company + team size when small
- Office location + role when uniquely identifying
- Project name + company when team is small
- Reporting structure details (reports to X who manages Y)

**Demographic combinations**
- Age + profession + small geographic area
- Rare medical condition + workplace
- Ethnicity + employer + department when unique
- Graduation year + university + major when small cohort
- Birth year + high school + sport team

**Behavioral patterns**
- Detailed daily schedules identifying a person
- Unique purchasing patterns + location
- Travel history that identifies an individual
- Device fingerprints with usage patterns
- Browsing history with identifying searches

**Professional identifiers**
- Medical license numbers
- Legal bar numbers
- Professional certification IDs
- Academic researcher IDs (ORCID when linked to sensitive data)
- Union membership numbers

---

## Category: credentials

**Authentication and access secrets** - data that grants access to systems, accounts, or resources.

### Must mask:

**API keys and tokens**
- AWS access keys: AKIA followed by 16 alphanumeric characters
- AWS secret keys: 40 character strings with the secret key
- Stripe keys: sk_live_*, pk_live_*, rk_live_*
- GitHub tokens: ghp_*, gho_*, ghu_*, ghs_*, ghr_*
- GitLab tokens: glpat-*
- Slack tokens: xoxb-*, xoxp-*, xoxa-*, xoxr-*
- Discord tokens: Bot tokens, webhook URLs with tokens
- SendGrid API keys: SG.*
- Twilio credentials: Account SID + Auth Token
- OpenAI API keys: sk-*
- Google API keys
- Azure API keys and connection strings
- Mailchimp API keys
- Datadog API keys
- PagerDuty API keys
- Generic API keys in environment variables or configs

**Passwords and passphrases**
- Plain text passwords in configurations
- Passwords shared in conversations
- Default passwords for systems
- Password hints that reveal the password
- Hashed passwords (especially MD5, SHA1)
- Password reset tokens
- One-time passwords (OTPs) for active sessions
- Master passwords for password managers

**Cryptographic keys and certificates**
- RSA private keys (-----BEGIN RSA PRIVATE KEY-----)
- EC private keys (-----BEGIN EC PRIVATE KEY-----)
- OpenSSH private keys (-----BEGIN OPENSSH PRIVATE KEY-----)
- PGP/GPG private keys
- SSL/TLS private keys
- JWT signing secrets
- Encryption keys for data at rest
- SSH private keys
- Certificate private keys
- Wallet private keys (cryptocurrency)
- Signing keys for code or documents

**Session and authentication tokens**
- Session IDs in URLs or cookies
- Bearer tokens
- OAuth access tokens
- OAuth refresh tokens
- SAML assertions
- JWT tokens containing sensitive claims
- Remember-me tokens
- Authentication cookies

**Recovery and backup codes**
- MFA backup codes
- Account recovery codes
- Security questions and answers
- Seed phrases for cryptocurrency wallets
- Recovery keys for encrypted devices
- Emergency access codes

**Database credentials**
- Connection strings with embedded passwords
- MongoDB URIs with credentials
- PostgreSQL connection strings
- MySQL connection strings
- Redis passwords
- Database admin credentials

---

## Category: financial

**Financial account information** - data enabling financial transactions or identity theft.

### Must mask:

**Payment card data**
- Full credit card numbers (13-19 digits, passes Luhn check)
- Debit card numbers
- Card expiration dates combined with card numbers
- CVV/CVC/CSC security codes
- Card PINs
- Virtual card numbers
- Prepaid card numbers

**Bank account information**
- Bank account numbers
- Routing numbers (ABA/ACH)
- IBAN (International Bank Account Number)
- SWIFT/BIC codes when combined with account info
- Wire transfer details
- Direct deposit information
- Check numbers with account details

**Investment account details**
- Brokerage account numbers
- Retirement account numbers (401k, IRA)
- Stock portfolio details with account numbers
- Trading account credentials
- Margin account details

**Tax and financial identifiers**
- Tax ID numbers (EIN, ITIN, SSN used for taxes)
- Tax return details with identifying information
- W-2 or 1099 form data
- Tax filing PINs
- Financial statement data with account holder info

**Cryptocurrency details**
- Private keys for wallets
- Seed phrases / recovery phrases
- Exchange account credentials
- Wallet passwords
- Transaction signing keys

---

## Category: medical

**Protected health information** - data covered by healthcare privacy regulations (HIPAA, etc.).

### Must mask:

**Medical records and identifiers**
- Medical record numbers (MRN)
- Health insurance ID numbers
- Medicare/Medicaid beneficiary numbers
- Prescription numbers
- Lab order numbers linked to patients
- Hospital admission numbers

**Health conditions and diagnoses**
- Specific diagnoses tied to identifiable individuals
- Mental health conditions with patient identity
- Substance abuse treatment information
- HIV/AIDS status with identity
- Genetic test results with patient info
- Cancer diagnoses with patient details
- Chronic condition details with patient identity

**Treatment information**
- Prescription drug names + dosages + patient identity
- Treatment plans with patient info
- Surgery details with patient identity
- Therapy session notes with patient info
- Rehabilitation program details
- Clinical trial participation with identity

**Provider-patient communications**
- Doctor's notes with patient identity
- Appointment details with patient info
- Test results with patient identity
- Medical advice given to specific patients
- Referral information with patient details

**Biometric health data**
- Blood type with patient identity
- Genetic markers with identity
- Vital signs history with patient info
- Medical imaging data with patient identity

---

## Category: location/precise

**Precise location data** - data enabling physical location of an individual.

### Must mask:

**Exact addresses**
- Full street addresses (number + street + city + postal code)
- Apartment/suite/unit numbers
- Building names with specific unit info
- Cross streets that identify exact location
- Landmark-relative directions to residences

**Geographic coordinates**
- GPS coordinates with high precision
- Latitude/longitude pairs identifying specific locations
- What3Words addresses
- Plus codes / Open Location Codes
- Geohashes at high precision

**Real-time and recent location**
- Current location data ("I'm at...")
- Recent check-ins or visits
- Location history revealing patterns
- Travel itinerary with specific times
- Commute patterns identifying home/work

**Vehicle identifiers**
- License plate numbers
- VIN (Vehicle Identification Number)
- Parking permit numbers
- Toll transponder IDs
- Fleet vehicle IDs linked to individuals

---

## Stage 1 Output Format (Risk Router)

**Implementation**: Stage 1 uses logit-based classification, not text generation.

The router extracts P(RISK) from a single forward pass by taking the softmax over
SAFE/RISK token logits. This is 5-6x faster than generating text tokens.

The score is a calibrated probability (0.0-1.0) indicating likelihood of PII:

Score interpretation:
- 0.0-0.3: Low risk, likely safe
- 0.3-0.6: Medium risk, may need review
- 0.6-1.0: High risk, likely contains PII

(For debugging/logging, the score can be formatted as `RISK 0.73`, but this is
not generated by the model in production.)

## Stage 2 Output Format (Span Redactor)

Stage 2 outputs the actual entity text to mask, not character offsets.

**Rationale**: LLMs are bad at counting characters but good at recognizing entities.
The masking engine then finds and replaces all occurrences using exact string matching.

```
PASS
MASK "john.doe@gmail.com" pii/direct
MASK "john.doe@gmail.com" pii/direct; MASK "sk_live_abc123" credentials
```

Format:
- `PASS` - no masking needed
- `MASK "<entity>" <category>` - mask the specified entity text
- Multiple entities separated by `; `
- Entity text is quoted to handle spaces and special characters
- Quotes within entities are escaped by doubling: `"say ""hello"""` → `say "hello"`

---

## Entity Extraction Rules

When extracting entities to mask:

1. **Extract the complete identifier** - output `john.doe@example.com` not `@example.com`
2. **Include all formatting** - output `(555) 123-4567` including parentheses, exactly as it appears
3. **Exclude surrounding prose** - from "My email is john@x.com", extract only `john@x.com`
4. **Output exactly as it appears** - preserve case, spacing, punctuation exactly
5. **Multiple identifiers** - "John Doe, 123 Main St, SSN 123-45-6789" → three separate entities

**Matching behavior**: The masking engine uses exact string matching, so output entities
precisely as they appear in the text. Case, whitespace, and punctuation must match exactly.

## Cross-Chunk Detection

When entities span chunk boundaries:
- Use overlap tail (last 64 chars of previous chunk) for context
- Extract the full entity text even if it started in the previous chunk
- Prefer over-masking (extract full entity) rather than partial leaks

---

## Decision Rules

1. **Mask** if the assistant response contains real PII or sensitive data
2. **Mask** spans in user prompts that contain PII (optional, configurable)
3. **Do NOT mask** clearly fictional or placeholder data (see harmless.md)
4. **Do NOT mask** educational content about PII without real examples
5. **Prefer over-masking** when uncertain - false positives are better than leaks
