# PII Constitution - Harmful (FAIL)

This constitution defines content that **SHOULD trigger PII detection** (label: FAIL).

We train classifiers to identify streaming voice conversation content that contains, reveals, or is imminently about to reveal personally identifiable information (PII).

---

## Category: person

**Personal identity information** - Full names, usernames, and handles that identify real individuals.

### Must flag (FAIL):

**Full names (first + last)**
- "My name is John Michael Smith"
- "This is Sarah Elizabeth Johnson calling"
- "I'm Robert Chen, account holder"
- "Can you look up the account for Maria Garcia-Lopez?"
- "Please update the name to William James Thompson III"
- "The order was placed by Jennifer Anne Wilson"
- "My husband David Christopher Brown authorized this"
- "Transfer to account holder Patricia Marie Davis"

**Full names in voice patterns (spelled out)**
- "That's J-O-H-N, space, S-M-I-T-H"
- "First name Sarah, S-A-R-A-H, last name Johnson, J-O-H-N-S-O-N"
- "It's spelled M-A-R-I-A, Garcia with a G"
- "Let me spell that: William, W-I-L-L-I-A-M"
- "My name is Robert, R as in Romeo, O-B-E-R-T"

**Full names with phonetic alphabet**
- "That's John, Juliet Oscar Hotel November"
- "Smith, Sierra Mike India Tango Hotel"
- "My last name is Chen, Charlie Hotel Echo November"
- "Brown, Bravo Romeo Oscar Whiskey November"

**Names combined with identifying context**
- "John Smith who lives at 123 Main Street"
- "Sarah Johnson, employee at Acme Corp"
- "My name is David Brown and my SSN is..."
- "This is Maria Garcia and my account number is..."
- "William Thompson, born January 15, 1985"
- "I'm Jennifer Wilson from the Springfield office"

**Partial names leading to full disclosure**
- "My name is John..." (when context suggests full name follows)
- "It's Sarah, Sarah John..." (partial last name starting)
- "First name is Michael, last name starts with Thomp..."
- "Call me Bob, full name Robert Wil..."

**Usernames/handles tied to real identity**
- "My Twitter handle is @JohnSmith1985"
- "Find me on Instagram as SarahJ_NYC"
- "My LinkedIn is linkedin.com/in/david-brown-engineer"
- "Username MariaG_Chicago on the app"
- "My gaming name is WillT_Gamer but real name is William Thompson"

---

## Category: contact

**Contact information** - Email addresses, phone numbers, mailing addresses.

### Must flag (FAIL):

**Email addresses (standard format)**
- "My email is john.smith@gmail.com"
- "Send it to sarah_j@company.com"
- "Contact me at david.brown.1985@yahoo.com"
- "My work email is maria.garcia@acmecorp.com"
- "Use jennifer.wilson@outlook.com"
- "Forward to billing@mycompany.net"
- "Personal email is robert_chen_nyc@hotmail.com"

**Email addresses (spelled out in voice)**
- "That's john dot smith at gmail dot com"
- "sarah underscore j at company dot com"
- "It's david period brown at yahoo period com"
- "maria dot garcia at acme corp dot com"
- "Send to jennifer dot wilson at outlook dot com"
- "J-O-H-N dot S-M-I-T-H at G-M-A-I-L dot com"

**Email addresses (obfuscated)**
- "john [at] smith [dot] gmail [dot] com"
- "My email is john, at symbol, company, dot, com"
- "It's sarah, the at sign, then yahoo, then dot com"
- "Email me at david, you know the at sign, gmail"

**Phone numbers (US formats)**
- "My number is 415-555-0123"
- "Call me at (212) 555-4567"
- "Reach me on 617.555.8901"
- "Phone: 310 555 2345"
- "Mobile is 4155550123"
- "My direct line is 1-800-555-6789"
- "+1 (415) 555-0123"

**Phone numbers (spelled out digit by digit)**
- "Four one five, five five five, zero one two three"
- "That's two one two, then five five five, then four five six seven"
- "Area code four one five, number five five five zero one two three"
- "My number is four-one-five, five-five-five, oh-one-two-three"
- "It's 4-1-5, then triple five, then 0-1-2-3"

**Phone numbers (international)**
- "+44 20 7946 0958"
- "My UK number is zero two zero seven nine four six..."
- "+33 1 42 68 53 00"
- "Call the Germany office at plus four nine..."
- "+81 3 1234 5678"

**Physical addresses (full)**
- "I live at 123 Main Street, Apartment 4B, New York, NY 10001"
- "Ship to 456 Oak Avenue, Suite 200, Los Angeles, CA 90012"
- "My address is 789 Elm Boulevard, Chicago, Illinois, 60601"
- "Send it to 321 Pine Road, Unit 15, San Francisco, California, 94102"
- "Deliver to 555 Maple Drive, Houston, Texas 77001"

**Physical addresses (partial but identifying)**
- "I'm at 123 Main Street in Manhattan"
- "The building is 456 Oak Avenue, suite two hundred"
- "Send to apartment 4B at 789 Elm..."
- "My house number is 321, on Pine Road"

**Addresses (spelled out)**
- "One two three Main Street"
- "Four five six Oak Avenue, that's O-A-K"
- "Apartment four bravo, or 4B"
- "Zip code one zero zero zero one"
- "Suite two zero zero, two hundred"

---

## Category: gov_id

**Government identification numbers** - SSN, passport, driver's license, tax IDs, national IDs.

### Must flag (FAIL):

**Social Security Numbers**
- "My SSN is 123-45-6789"
- "Social is one two three, four five, six seven eight nine"
- "Social security number: 123456789"
- "Last four of my social is 6789"
- "My social starts with 123..."

**SSN (spelled out/obfuscated)**
- "One two three, dash, four five, dash, six seven eight nine"
- "First three digits are one two three, middle two are four five"
- "SSN is one-two-three, forty-five, sixty-seven-eighty-nine"
- "Social is 123, then 45, then 6789"

**Driver's license numbers**
- "My license number is D12345678"
- "California DL: Y1234567"
- "New York license A123 456 789 012"
- "Texas driver's license 12345678"
- "My DL is Florida number G123-456-78-901-0"

**Passport numbers**
- "Passport number 123456789"
- "My US passport is 987654321"
- "UK passport number GBR 12345678"
- "Passport: AB1234567"

**Tax identification numbers**
- "My EIN is 12-3456789"
- "ITIN: 9XX-XX-XXXX"
- "Tax ID number is twelve, three four five six seven eight nine"
- "Federal tax ID: 123456789"

**National ID numbers (international)**
- "My NIE is X1234567A"
- "UK National Insurance number AB123456C"
- "Aadhaar number is 1234 5678 9012"
- "Canadian SIN: 123 456 789"
- "Australian TFN: 123 456 789"
- "German Steuer-ID: 12345678901"

**Partial government IDs (streaming)**
- "My SSN starts with one two three..."
- "License number D one two three four..."
- "First five of my passport are one two..."
- "Social security is one two three, forty..."

---

## Category: financial

**Financial account information** - Credit cards, bank accounts, routing numbers, crypto wallets.

### Must flag (FAIL):

**Credit card numbers**
- "Card number is 4532 1234 5678 9012"
- "My Visa is 4111111111111111"
- "Credit card: 5500 0000 0000 0004"
- "The Amex is 378282246310005"
- "Card ending in 9012, full number is 4532..."

**Credit cards (digit by digit)**
- "Four five three two, one two three four, five six seven eight, nine zero one two"
- "That's four-five-three-two, then one-two-three-four..."
- "First four digits are four five three two"
- "Card number starting with four five three..."

**Card security information**
- "CVV is 123"
- "Security code on the back is four five six"
- "The three digit code is 789"
- "Expiration is oh three twenty six" (03/26)
- "Expires March 2026, CVV 123"

**Bank account numbers**
- "Account number is 12345678901234"
- "My checking account: 9876543210"
- "Savings account number 1234567890123456"
- "Bank account ending in 1234, full number is..."

**Routing numbers**
- "Routing number 021000021"
- "ABA number is zero two one zero zero zero zero two one"
- "Wire routing: 121000358"
- "ACH routing number 026009593"

**IBAN and international banking**
- "IBAN: GB82 WEST 1234 5698 7654 32"
- "My IBAN is GB82WEST12345698765432"
- "German IBAN DE89370400440532013000"
- "SWIFT code CHASUS33"

**Cryptocurrency wallets**
- "My Bitcoin address is 1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
- "ETH wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f..."
- "Send to wallet address starting with one B v B M S..."
- "My Coinbase wallet is..."

**Partial financial info (streaming)**
- "Card number is four five three two, one two..."
- "Account starts with nine eight seven..."
- "First eight digits of the routing number are zero two one..."
- "The IBAN begins with GB eight two..."

---

## Category: credentials

**Authentication secrets** - Passwords, API keys, tokens, PINs, security codes.

### Must flag (FAIL):

**Passwords**
- "My password is MyS3cr3tP@ss!"
- "The login password is Welcome123"
- "Account password: admin2024"
- "I set the password to Fluffy#Cat99"
- "Current password is OldPass123, new one is NewPass456"

**Passwords (spelled out)**
- "Password is capital M, y, capital S, three, c, r, three, t..."
- "It's W-E-L-C-O-M-E-one-two-three"
- "The password is whiskey echo lima charlie oscar mike echo"
- "Set it to capital F, l-u-f-f-y, hash symbol, capital C, a-t, nine nine"

**API keys and tokens**
- "My API key is sk_live_abc123xyz789def456"
- "The token is ghp_xxxxxxxxxxxxxxxxxxxx"
- "AWS access key AKIAIOSFODNN7..."
- "Stripe key sk_live_..."
- "OpenAI key sk-proj-..."

**PINs and security codes**
- "My PIN is 1234"
- "ATM PIN: 5678"
- "Security PIN is four five six seven"
- "The passcode is one two three four"
- "Verification PIN: 987654"

**MFA codes and backup codes**
- "The verification code is 123456"
- "OTP is 789012"
- "My authenticator shows 345678"
- "Backup code is ABCD-EFGH-IJKL"
- "Two factor code: 567890"

**Recovery phrases (crypto)**
- "Seed phrase is abandon abandon abandon..."
- "Recovery words: apple banana cherry..."
- "My twelve words are elephant tiger lion..."
- "Wallet backup phrase starts with ocean..."

**Database credentials**
- "MySQL password is db_admin_2024"
- "Postgres connection: user admin password secretpass"
- "MongoDB URI mongodb://user:pass@..."
- "Redis password is cache_secret_123"

---

## Category: medical

**Protected health information** - Diagnoses, conditions, prescriptions, medical record numbers.

### Must flag (FAIL):

**Medical record numbers**
- "My MRN is 12345678"
- "Medical record number: MRN-9876543"
- "Patient ID is 456789012"
- "Hospital record number starting with MR..."

**Health insurance IDs**
- "Insurance ID is ABC123456789"
- "My policy number is XYZ987654321"
- "Member ID: 123456789-01"
- "Medicare number 1EG4-TE5-MK72"
- "Medicaid ID 12345678901"

**Diagnoses with patient identity**
- "I'm John Smith and I was diagnosed with Type 2 diabetes"
- "My doctor told me, Sarah Johnson, that I have hypertension"
- "The oncologist said I have stage 2 breast cancer"
- "I was just diagnosed with bipolar disorder"
- "They found I have hepatitis C"

**Prescriptions with patient identity**
- "I'm calling about my prescription for Lisinopril 10mg"
- "Dr. Jones prescribed me Metformin 500mg twice daily"
- "I need a refill on my Adderall 20mg"
- "My Oxycodone prescription number is RX123456"
- "I take Prozac 40mg for my depression"

**Mental health information**
- "I'm in treatment for PTSD"
- "My therapist diagnosed me with anxiety disorder"
- "I've been hospitalized for schizophrenia"
- "I'm in an outpatient program for addiction"
- "My psychiatrist says I have major depression"

**HIV/AIDS status**
- "I'm HIV positive"
- "My viral load test results..."
- "I'm on antiretroviral therapy"
- "CD4 count is..."

**Genetic information**
- "My genetic test showed BRCA1 mutation"
- "I carry the gene for Huntington's"
- "23andMe results show I'm a carrier for..."

---

## Category: location

**Precise location information** - Exact addresses, GPS coordinates, real-time location.

### Must flag (FAIL):

**GPS coordinates**
- "I'm at coordinates 37.7749, -122.4194"
- "GPS location is 40.7128 north, 74.0060 west"
- "Latitude 34.0522, longitude -118.2437"
- "My current position is 51.5074, -0.1278"

**Real-time location**
- "I'm currently at 123 Main Street"
- "Right now I'm at the corner of 5th and Broadway"
- "I'm standing outside 456 Oak Avenue"
- "My current location is the Starbucks on Market Street"
- "I'm at home right now at 789 Elm..."

**Home address**
- "I live at 123 Main Street, Apartment 4B"
- "My home address is 456 Oak Avenue"
- "Residence: 789 Elm Boulevard, Unit 201"
- "I stay at 321 Pine Road"

**Work address (specific)**
- "I work at 100 Corporate Drive, Building B, 3rd floor"
- "My office is at 555 Market Street, Suite 1200"
- "Come to my workplace at 123 Industrial Way"

**Vehicle identifiers**
- "License plate is ABC1234"
- "My plate number is 7XYZ890"
- "VIN: 1HGBH41JXMN109186"
- "Vehicle identification number is..."
- "Registration plate California 8ABC123"

**Tracking/location device IDs**
- "Toll transponder number 12345678"
- "My E-ZPass ID is..."
- "Fleet vehicle ID FLT-123456"
- "GPS tracker ID..."

---

## Category: identifier

**Unique identifiers** - Order numbers, account IDs, device IDs, IP addresses, tracking numbers.

### Must flag (FAIL):

**Order numbers**
- "Order number is 789012345"
- "My order ID: ORD-2024-12345"
- "Reference number 123-456-789"
- "Confirmation number ABC123XYZ"
- "Order #1234567890"

**Account/Customer IDs**
- "My account ID is 8834729103"
- "Customer number: CUST-123456"
- "Member ID 987654321"
- "Account reference: ACC-2024-001234"
- "User ID is USR_abc123xyz"

**Tracking numbers**
- "FedEx tracking 1234567890123456789012"
- "UPS tracking number 1Z999AA10123456784"
- "USPS: 9400111899223033005012"
- "DHL tracking 1234567890"

**Device identifiers**
- "IMEI number 353456789012345"
- "My device ID is..."
- "Serial number SN123456789"
- "MAC address 00:1A:2B:3C:4D:5E"
- "Hardware ID HW-123-456-789"

**IP addresses (personal/identifying)**
- "My IP address is 98.234.12.45"
- "Connect from 192.168.1.105" (when context identifies person)
- "The IP is 76.12.34.56"
- "IPv6 address 2001:0db8:85a3:0000:0000:8a2e:0370:7334"

**Session/Transaction IDs (with user context)**
- "Transaction ID TXN-2024-123456 for my account"
- "Session ID sess_abc123xyz789"
- "Reference: REF-123456789"
- "Case number CASE-2024-001234"
- "Ticket ID TKT-987654"

---

## Cross-Category: Combinations and Context

### Must flag (FAIL):

**Name + any other PII**
- "John Smith, phone 415-555-0123"
- "Sarah Johnson at sarah.j@gmail.com"
- "David Brown, SSN 123-45-6789"
- "Maria Garcia, account 12345678"

**Partial PII being streamed**
- "My SSN is one two three..." (clearly continuing)
- "Email is john dot smith at..." (email in progress)
- "Card number four five three two..." (card being read)
- "Phone is four one five..." (number in progress)

**Implicit imminent PII disclosure**
- "Let me give you my social security number..." (about to provide)
- "I'll read you the card number now..." (about to provide)
- "Here's my address..." (about to provide)
- "OK, my password is..." (about to provide)

**Obfuscated PII (voice patterns)**
- "Email is john AT gmail DOT com"
- "Phone: four-one-five, triple-five, oh-one-two-three"
- "SSN: one-two-three, forty-five, sixty-seven-eighty-nine"
- "Card: four-five-three-two (pause) one-two-three-four..."

---

## Voice-Specific Patterns

### Must flag (FAIL):

**Self-corrections revealing PII**
- "My number is 415... wait, 416-555-0123"
- "Email john.smith... no, john_smith@gmail.com"
- "SSN one two four... sorry, one two three, four five..."

**Hesitant/broken PII disclosure**
- "My social is... um... one two three... let me check... four five..."
- "The card number, hold on... four five three two..."
- "Email is... john... dot... smith... at..."

**Agent-prompted PII response**
- "Agent: What's your SSN? User: It's one two three..."
- "Agent: Can I get your email? User: Sure, john dot smith at..."
- "Agent: And your phone number? User: Four one five..."

**Dictation-style PII**
- "Writing this down: John Smith, 123 Main Street, 415-555-0123"
- "Got it: SSN 123-45-6789, DOB January 15 1985"
- "For the record: account 12345678, routing 021000021"

---

## Notes for Synthetic Data Generation

Use this constitution to generate:

1. **Positive examples (FAIL cases)**
   - Complete PII disclosures in natural voice conversation
   - Partial/streaming PII disclosures
   - Spelled-out and obfuscated PII
   - PII in response to agent prompts

2. **Hard positives (subtle but still PII)**
   - PII combined with names
   - Self-corrections that reveal PII
   - Hesitant disclosures
   - Multi-turn PII accumulation

3. **Context-dependent PII**
   - Same identifier in personal vs business context
   - Account numbers with vs without name association
   - Addresses in delivery vs identification context
