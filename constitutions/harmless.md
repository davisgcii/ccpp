# Harmless Constitution

This constitution defines content that **should NOT trigger masking**, organized into three categories following Constitutional Classifiers methodology:

1. **PII-Related Harmless Content** - Content that resembles PII but is explicitly safe
2. **Unrelated Potentially Suspicious Content** - Non-PII content that might superficially trigger detection
3. **General Harmless Content** - Clearly benign content unrelated to PII

---

## 1. PII-Related Harmless Content

Content that relates to the PII domain but should NOT be masked.

### Placeholder and Template Patterns

**Standard template variables**
- `<EMAIL>`, `<PHONE>`, `<ADDRESS>`, `<NAME>`
- `{{user_email}}`, `{{phone_number}}`, `{{api_key}}`
- `${EMAIL}`, `${PHONE}`, `${SSN}`, `${API_KEY}`
- `[EMAIL]`, `[REDACTED]`, `[MASKED]`, `[REMOVED]`
- `YOUR_API_KEY_HERE`, `INSERT_TOKEN_HERE`, `REPLACE_ME`
- `<insert email>`, `<your phone here>`, `<enter address>`
- `___@___.com` format placeholders
- `XXX-XX-XXXX` format placeholders
- `****-****-****-****` masked values

**Reserved example domains (RFC 2606 / RFC 6761)**
- `example.com`, `example.org`, `example.net`
- `test.example.com`, `foo.example.org`, `api.example.net`
- `*.test`, `*.invalid`, `*.localhost`, `*.example`
- `user@example.com`, `admin@example.org`, `test@example.net`
- `john.doe@example.com`, `jane.smith@example.org`
- `noreply@example.com`, `support@example.net`
- `info@example.com`, `contact@example.org`

**Reserved example IP addresses (RFC 5737)**
- `192.0.2.0/24` (TEST-NET-1): 192.0.2.1, 192.0.2.100, etc.
- `198.51.100.0/24` (TEST-NET-2): 198.51.100.1, etc.
- `203.0.113.0/24` (TEST-NET-3): 203.0.113.1, etc.
- `0.0.0.0`, `127.0.0.1` (localhost)
- `::1` (IPv6 localhost)

**Reserved phone numbers**
- US `555-0100` through `555-0199` (fictional)
- US `555-1212` (directory assistance)
- `555-555-5555`, `(555) 555-5555`
- `+1-555-555-5555`, `1-555-555-5555`
- `123-456-7890` (obvious placeholder)
- `000-000-0000`, `999-999-9999`
- `+1 (800) EXAMPLE`

### Test and Demo Credentials

**Test credit card numbers (official test numbers)**
- `4111111111111111` (Visa test card)
- `4012888888881881` (Visa test card)
- `5500000000000004` (Mastercard test)
- `5555555555554444` (Mastercard test)
- `378282246310005` (American Express test)
- `371449635398431` (American Express test)
- `6011111111111117` (Discover test)
- `6011000990139424` (Discover test)
- `3530111333300000` (JCB test)
- Test card numbers from Stripe, PayPal, Braintree documentation

**Test API keys (documented examples)**
- `sk_test_*` (Stripe test mode keys)
- `pk_test_*` (Stripe publishable test keys)
- `AKIAIOSFODNN7EXAMPLE` (AWS example access key)
- `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` (AWS example secret)
- `ABCDEFGHIJKLMNOPQRSTUVWXYZ` (obvious placeholder)
- `1234567890abcdef` (obvious placeholder)
- Keys explicitly marked as "example", "test", "demo", "sample"
- Keys from official documentation or tutorials

**Test SSN and government IDs**
- `123-45-6789` (obvious placeholder)
- `000-00-0000`, `999-99-9999`
- SSNs starting with `9XX` (not issued)
- SSNs with `00` in middle group (not issued)
- `XXX-XX-XXXX`, `NNN-NN-NNNN`
- Any SSN in format explanations

**Test addresses**
- `123 Main Street`, `123 Test Street`, `123 Example Ave`
- `1 Infinite Loop` (Apple HQ - public)
- `1600 Amphitheatre Parkway` (Google HQ - public)
- `410 Terry Avenue North` (Amazon HQ - public)
- Addresses ending in "Anytown, USA" or "Springfield"
- Addresses with ZIP codes `12345`, `00000`, `99999`

### Educational and Documentation Content

**Explaining PII concepts without real examples**
- "An email address typically follows the format user@domain.com"
- "Social Security Numbers follow the pattern XXX-XX-XXXX"
- "Credit cards are typically 13-19 digits and use Luhn validation"
- "API keys often start with service-specific prefixes like sk_, pk_"
- Discussions of what constitutes PII under GDPR, CCPA, HIPAA
- Explanations of data protection regulations
- Privacy policy templates without real data
- Security training materials explaining attack vectors

**Code examples showing patterns (not real data)**
- Regex patterns: `\b\d{3}-\d{2}-\d{4}\b`
- Validation functions: `isValidEmail(input)`
- Schema definitions: `email: string, phone: string`
- Input sanitization examples
- Data masking function demonstrations
- Encryption/hashing code examples

**Form field labels and UI elements**
- "Email:" (the label, not a value)
- "Phone Number:", "Address:", "SSN:"
- "Enter your email address below"
- Placeholder text: "name@company.com"
- Input field descriptions
- Help text explaining required formats

### Anonymized and Redacted Data

**Properly masked values**
- `j***@example.com` (partially masked email)
- `***-**-6789` (partially masked SSN)
- `****-****-****-1234` (masked card number)
- `[REDACTED]`, `[REMOVED]`, `[MASKED]`
- `<email removed>`, `<address withheld>`
- Hash references: `user_abc123`, `account_xyz789`

**Aggregated statistics**
- "Average age of users: 34"
- "10,000 customers in California"
- "Most common email domain: gmail.com"
- Demographic percentages without individual data
- Usage statistics without user identification

**Synthetic/generated identifiers**
- UUIDs: `550e8400-e29b-41d4-a716-446655440000`
- Random hashes: `a1b2c3d4e5f6...`
- Sequential IDs: `USER_001`, `ACCOUNT_12345`
- Timestamps as identifiers

### Public and Business Information

**Public company information**
- Corporate headquarters addresses
- Investor relations contact info
- Press contact information
- General customer service numbers (1-800 numbers)
- Company websites and general email formats
- SEC filings and public financial data

**Public figures' official contacts**
- Official government office contact info
- Published book author contact via publisher
- Academic institution contact information
- Publicly listed business addresses
- Press representative contact info

**Generic business references**
- "Contact our support team at support@..."
- "Call our main number at 1-800-..."
- Industry-standard formats without specific data
- Generic org charts and role descriptions

---

## 2. Unrelated Potentially Suspicious Content

Content that might superficially trigger detection but is NOT PII.

### Numbers and Codes That Resemble PII

**Product and part numbers**
- SKU numbers: `SKU-1234567890`
- Part numbers: `PN-2345-6789-0123`
- Serial numbers: `S/N: 123456789012345`
- Model numbers: `Model XR-5500-PRO`
- Barcode numbers (UPC, EAN)
- ISBN numbers for books
- VIN-like product codes (not actual vehicles)

**Technical identifiers**
- MAC addresses: `00:1A:2B:3C:4D:5E`
- Hardware serial numbers
- Software license keys (format varies)
- Package tracking numbers (FedEx, UPS, USPS)
- Order confirmation numbers
- Ticket/case numbers

**Scientific notation and data**
- Coordinate systems (not GPS): `x: 123.45, y: 678.90`
- Chemical formulas: `C6H12O6`
- Mathematical constants: `3.14159265358979`
- Statistical values: `p < 0.001, r² = 0.95`
- Measurement units: `123.456 kg`, `78.9 meters`

**Dates and times (without identity context)**
- Timestamps: `2024-01-15T10:30:00Z`
- Unix timestamps: `1705312200`
- Date ranges: `January 1 - December 31, 2024`
- Historical dates: `July 4, 1776`
- Scheduling times without personal context

### Code and Technical Content

**Source code (not containing secrets)**
- Variable names: `userEmail`, `phoneNumber`, `apiKey`
- Function signatures: `def validate_email(email: str)`
- Class definitions with PII-like field names
- Database schema with column names
- API endpoint definitions
- Config file structures (without real values)

**Network and system information**
- Localhost references: `127.0.0.1`, `localhost`
- Private IP ranges: `192.168.*.*`, `10.*.*.*`, `172.16-31.*.*`
- Port numbers: `:8080`, `:443`, `:22`
- Protocol references: `https://`, `ssh://`, `ftp://`
- Domain names that are clearly technical

**Log formats and examples**
- Timestamp + log level patterns
- Stack traces with file paths
- Error messages with codes
- Debug output formats
- Metric names and values

### Financial and Business Numbers

**Public financial data**
- Stock prices: `$123.45`
- Market cap figures
- Revenue numbers (public companies)
- Exchange rates
- Interest rates
- Index values (S&P 500, NASDAQ)

**Generic account references**
- Account types: "savings account", "checking account"
- Generic balance: "account balance: $X,XXX.XX"
- Transaction types without specifics
- Banking terms and definitions
- Investment terminology

---

## 3. General Harmless Content

Clearly benign content unrelated to PII detection.

### Educational and Informational

- Explaining how encryption works
- Describing data protection best practices
- Teaching programming concepts
- Explaining database design principles
- Discussing privacy regulations conceptually
- Security awareness training content
- Compliance framework overviews
- Technology tutorials and guides
- Academic research discussions
- Historical information
- Scientific explanations
- Cultural and social topics

### Creative and Entertainment

- Fiction writing and storytelling
- Poetry and creative writing
- Game descriptions and walkthroughs
- Movie and book reviews
- Music discussions
- Art and design topics
- Sports statistics and analysis
- Travel descriptions (without personal itineraries)
- Food and cooking recipes
- Hobby and craft instructions

### Business and Professional

- Generic business advice
- Career guidance
- Interview preparation tips
- Resume writing advice (format, not content)
- Meeting agenda templates
- Project management concepts
- Team collaboration tips
- Professional development
- Industry news and trends
- Market analysis

### Technical (Non-Sensitive)

- Open source software documentation
- Programming language tutorials
- Algorithm explanations
- System architecture discussions
- Cloud computing concepts
- DevOps practices
- Testing methodologies
- Code review practices
- Version control workflows
- CI/CD pipeline concepts

### Health and Wellness (General)

- General fitness advice
- Nutrition information
- Sleep hygiene tips
- Stress management techniques
- Exercise routines
- Healthy eating guidelines
- Mental wellness concepts
- Meditation and mindfulness
- Work-life balance tips
- Ergonomics advice

---

## Validation Rules for Heuristics

When heuristics flag potential PII, apply these validation rules:

1. **Check example domains** - If email domain is `example.com/org/net`, `test`, `invalid`, `localhost` → SAFE
2. **Check 555 numbers** - If US phone starts with `555-01XX` or `555-555` → SAFE
3. **Check test cards** - If passes Luhn but matches known test card patterns → SAFE
4. **Check placeholders** - If wrapped in `<>`, `{{}}`, `[]`, or contains `EXAMPLE`, `TEST`, `YOUR_*_HERE`, `SAMPLE`, `DEMO` → SAFE
5. **Check AWS examples** - If matches `AKIAIOSFODNN7EXAMPLE` → SAFE
6. **Check Stripe test keys** - If starts with `sk_test_` or `pk_test_` → SAFE
7. **Check RFC reserved IPs** - If in `192.0.2.*`, `198.51.100.*`, `203.0.113.*` → SAFE
8. **Check context** - If in clearly educational/documentation context explaining formats → SAFE

---

## Notes for Synthetic Data Generation

Use this constitution to generate:

1. **Negative examples** (content that should NOT be masked)
   - Conversations using placeholder data
   - Educational content about PII
   - Code examples with example.com domains

2. **Hard negatives** (look like PII but aren't)
   - Test credit card numbers
   - 555 phone numbers
   - example.com email addresses
   - AWS example keys

3. **Context-dependent examples**
   - Same pattern in safe vs unsafe contexts
   - Documentation vs actual data
   - Public vs private information

The classifier must learn to distinguish:
- `john.doe@example.com` → SAFE (placeholder domain)
- `john.doe@gmail.com` → MASK (real email)
- `sk_test_abc123` → SAFE (test mode)
- `sk_live_abc123` → MASK (production key)
- `555-555-5555` → SAFE (reserved fake)
- `555-123-4567` → MASK (real number)
- "Email format: user@domain.com" → SAFE (educational)
- "My email is john@real.com" → MASK (actual PII)
