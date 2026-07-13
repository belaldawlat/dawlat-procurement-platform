# Dawlat Procurement Platform
## Product and Engineering Blueprint

**Business:** Dawlat Global Imports & Trading  
**Product:** Dawlat Procurement Platform  
**Purpose:** Manage global sourcing, procurement, logistics, landed cost, inventory, sales, finance, documents, analytics, and internal automation in one secure platform.

---

# 1. Product Vision

Dawlat Procurement Platform will become the operating system for Dawlat Global Imports & Trading.

The platform will manage the complete business journey:

Supplier discovery  
→ Supplier verification  
→ RFQ creation  
→ Supplier quotations  
→ Freight and customs quotations  
→ Warehouse and 3PL quotations  
→ Landed-cost calculation  
→ Supplier selection  
→ Purchase order  
→ Shipment tracking  
→ Customs and biosecurity  
→ Warehouse delivery  
→ Inventory  
→ Customer quotation  
→ Sales order  
→ Invoice  
→ Payment  
→ Analytics

Automation and intelligence will operate internally. External communication must always appear professional and come from Dawlat Global Imports & Trading.

---

# 2. Core Principles

The platform must be:

- Secure
- Scalable
- Modular
- Maintainable
- Auditable
- Reliable
- Mobile-friendly
- Accessible
- Fast
- Cloud-ready
- API-first
- Multi-user
- Role-based
- Testable
- Observable
- Privacy-focused
- Suitable for future SaaS use

No module should depend directly on page code.

Business logic must be separated into:

- Views
- Services
- Repositories
- Models
- Database
- Integrations
- Automation
- Analytics
- Security

---

# 3. User Types

## Owner / Super Admin
Full platform access.

## Administrator
Manage users, settings, roles, company information, and system configuration.

## Procurement Manager
Manage suppliers, RFQs, quotations, products, samples, purchase orders, and supplier comparisons.

## Logistics Manager
Manage freight forwarders, customs brokers, ports, warehouses, inspections, shipments, and delivery.

## Sales Manager
Manage customers, quotations, orders, pricing, and customer communication.

## Finance Manager
Manage invoices, payments, costs, taxes, landed cost, margins, and financial reporting.

## Viewer
Read-only access to approved modules.

---

# 4. Authentication and Security

The platform must support:

- Secure login
- Logout
- Password hashing
- Password changes inside the app
- Password reset
- User creation
- User activation and deactivation
- Roles and permissions
- Session management
- Audit logs
- Login history
- Failed-login tracking
- Account lockout
- Optional multi-factor authentication
- Secrets stored outside source code
- Private business data excluded from GitHub
- Database backups
- Encrypted production traffic
- File access permissions

The `.env` file may only bootstrap the first administrator account. After first setup, user management must be controlled from the application database.

---

# 5. Partner Directory

The Partner Directory will store every organisation involved in global trade.

## Partner Types

- Supplier
- Manufacturer
- Exporter
- Distributor
- Freight Forwarder
- Customs Broker
- Port Operator
- Shipping Line
- Warehouse
- 3PL Provider
- Local Transport Company
- Inspection Company
- Certification Company
- Insurance Provider
- Bank
- Foreign Exchange Provider
- Packaging Supplier
- Government Agency
- Customer
- Sales Agent
- Consultant

## Partner Profile Fields

- Company name
- Trading name
- Partner type
- Country
- State
- City
- Address
- Website
- Email
- Phone
- WhatsApp
- Contact person
- Job title
- Products or services
- Countries served
- Certifications
- Licences
- Export markets
- Years in business
- Production capacity
- Preferred ports
- Payment terms
- Incoterms
- MOQ
- Lead time
- Notes
- Status
- Risk level
- Internal rating
- Verification status
- Last contact date
- Next follow-up date
- Documents
- Communication history
- Linked quotations
- Linked shipments
- Linked invoices
- Linked tasks

---

# 6. Supplier Management

The Supplier CRM must support:

- Add supplier
- Edit supplier
- Delete supplier
- Search
- Filter
- Tags
- Status
- Rating
- Verification
- Preferred supplier flag
- Blacklist
- Product linkage
- Contact history
- Documents
- Certificates
- Samples
- Quotations
- Notes
- Tasks
- Follow-up reminders
- Performance history
- Supplier score
- Export to CSV
- Export to Excel

## Supplier Statuses

- Prospect
- Contacted
- Awaiting Reply
- Qualified
- Sample Requested
- Sample Received
- Approved
- Preferred
- On Hold
- Inactive
- Rejected
- Blacklisted

---

# 7. Global Supplier Discovery

The platform must search for current supplier and service-provider information from live and trusted sources.

## Search Targets

- Manufacturers
- Exporters
- Wholesalers
- Freight forwarders
- Customs brokers
- Warehouses
- 3PL providers
- Port service companies
- Shipping companies
- Inspection providers
- Packaging companies

## Search Filters

- Product
- Country
- Region
- Certificate
- Export market
- MOQ
- Incoterm
- Port
- Supplier type
- Company size
- Product category
- Verified status

## Data Sources

The platform should support:

- Company websites
- Government exporter directories
- Trade associations
- Trade-fair directories
- Industry directories
- Public company registries
- Shipping and logistics directories
- Australian government sources
- Supplier marketplaces where legally and technically permitted
- User-uploaded files
- Internal historical data

## Discovery Workflow

Search  
→ Collect candidate companies  
→ Remove duplicates  
→ Validate website  
→ Extract contacts  
→ Extract products  
→ Extract certificates  
→ Assign confidence score  
→ Flag missing information  
→ Save selected companies  
→ Generate outreach  
→ Track response

Every discovered company must be marked with:

- Source
- Search date
- Verification date
- Confidence level
- Evidence links
- Last updated date

No discovered company should automatically be treated as verified.

---

# 8. Product Catalogue

The system must manage:

- Product categories
- Products
- Product variants
- Specifications
- Units
- Packaging
- Country of origin
- Certificates required
- Import conditions
- Supplier relationships
- Historical prices
- Samples
- Documents
- Images
- Barcodes
- Internal SKU
- Customer SKU
- Storage requirements
- Expiry tracking
- Batch tracking

## Initial Product Categories

- Rice
- Cricket Equipment
- Automotive Parts
- Medical Supplies
- Packaging
- Other

## Initial Rice Types

- ST25
- Jasmine
- Basmati
- Sella
- Raw Rice
- Long Grain
- Medium Grain

---

# 9. RFQ Management

The RFQ module must support:

- Create RFQ
- Generate RFQ number
- Select suppliers
- Select products
- Add specifications
- Add quantity
- Add packaging requirements
- Add certificates
- Add destination
- Add preferred Incoterms
- Add sample requirements
- Add delivery timeline
- Add payment requirements
- Add required documents
- Generate email
- Save draft
- Send
- Track status
- Track supplier response
- Set deadline
- Send follow-up
- Close RFQ
- Duplicate RFQ
- Convert quotation into purchase order

## RFQ Statuses

- Draft
- Ready
- Sent
- Partially Responded
- Fully Responded
- Under Review
- Awarded
- Closed
- Cancelled

---

# 10. Supplier Quotations

Each supplier quotation must store:

- Quotation number
- Supplier
- RFQ
- Product
- Specification
- Quantity
- Unit
- Unit price
- Currency
- MOQ
- Packaging
- Incoterm
- Origin port
- Destination port
- Lead time
- Production time
- Transit time
- Payment terms
- Sample cost
- Sample shipping
- Certificates
- Export documents
- Valid-until date
- Freight included
- Insurance included
- Notes
- Attached files
- Parsed data confidence
- Approval status

The platform must preserve historical quotation versions.

---

# 11. Supplier Comparison

The comparison engine must evaluate:

- Product price
- Freight
- Insurance
- MOQ
- Quality
- Certificates
- Packaging
- Lead time
- Payment terms
- Export experience
- Response speed
- Communication quality
- Sample quality
- Supplier reliability
- Country risk
- Currency risk
- Shipping risk
- Compliance risk
- Historical performance
- Total landed cost

The platform must explain recommendations clearly.

Example:

Supplier A is not the cheapest factory option, but has a lower total landed cost because freight, packaging, lead time, and compliance risk are better.

---

# 12. Freight and Customs

The platform must manage Australian and international logistics providers.

## Freight Forwarders

Store:

- Company
- Contact
- Routes
- Sea freight
- Air freight
- Road freight
- Rail freight
- FCL
- LCL
- Container types
- Rates
- Transit times
- Origin charges
- Destination charges
- Insurance
- Validity period
- Notes
- Performance score

## Customs Brokers

Store:

- Company
- Contact
- Australian Border Force experience
- DAFF and biosecurity experience
- Food-import experience
- Medical-import experience
- Automotive-import experience
- Customs-entry fee
- Biosecurity coordination fee
- Inspection coordination
- Port coordination
- Delivery coordination
- Quote history
- Rating
- Notes

## Ports and Container Services

Store:

- Port
- Terminal
- Container handling
- Demurrage
- Detention
- Storage
- Unpacking
- Container transport
- Empty-container return
- Delivery to warehouse

---

# 13. Warehouses and 3PL

The platform must support:

- Warehouse directory
- Melbourne
- Sydney
- Brisbane
- Adelaide
- Perth
- Regional locations
- Pallet storage
- Container unloading
- Pick and pack
- Distribution
- Cold storage
- Food-grade storage
- Medical-grade storage
- Bonded storage
- Inventory integration
- Storage quotations
- Delivery quotations
- Capacity
- Minimum commitment
- Insurance
- Service-level agreements

---

# 14. Landed Cost Engine

The system must calculate:

Supplier product cost  
+ Packaging  
+ Inland origin transport  
+ Export clearance  
+ Origin port charges  
+ Freight  
+ Marine insurance  
+ Currency conversion  
+ Australian port charges  
+ Customs broker fees  
+ Biosecurity inspection  
+ Duty  
+ GST  
+ Container transport  
+ Unpacking  
+ Warehouse delivery  
+ Storage  
+ Other costs  
= Total landed cost

The system must calculate:

- Total shipment cost
- Cost per kilogram
- Cost per carton
- Cost per bag
- Cost per pallet
- Cost per unit
- Cost by supplier
- Cost by route
- Cost by Incoterm
- Cost by currency
- Scenario comparison
- Break-even price
- Recommended selling price
- Margin estimate

Profit and margin information must remain internal and must never appear in supplier communication.

---

# 15. Purchase Orders

Purchase Orders must support:

- Purchase order number
- Supplier
- RFQ
- Approved quotation
- Products
- Quantities
- Prices
- Currency
- Incoterm
- Payment terms
- Delivery date
- Shipping instructions
- Packaging instructions
- Documents
- Approval workflow
- Status
- Change history
- Supplier acknowledgement

---

# 16. Shipment Management

Shipment records must include:

- Shipment number
- Purchase order
- Supplier
- Freight forwarder
- Customs broker
- Shipping line
- Origin port
- Destination port
- Container number
- Container type
- Bill of lading
- Booking number
- ETD
- ETA
- Actual departure
- Actual arrival
- Customs status
- Biosecurity status
- Inspection status
- Delivery status
- Warehouse
- Documents
- Costs
- Notes
- Tasks
- Exceptions
- Delays
- Notifications

---

# 17. Documents

The Document Centre must store:

- Supplier catalogues
- Quotations
- Commercial invoices
- Packing lists
- Bills of lading
- Certificates of origin
- Phytosanitary certificates
- Fumigation certificates
- Quality certificates
- Halal certificates
- ISO certificates
- HACCP certificates
- Insurance certificates
- Customs documents
- Purchase orders
- Sales invoices
- Contracts
- Product specifications
- Inspection reports
- Warehouse documents

Each document must support:

- Upload
- Download
- Preview
- Version history
- Tags
- Linked business record
- Expiry date
- Access permissions
- Search
- Data extraction
- Audit history

---

# 18. Inventory

Inventory must support:

- Products
- SKUs
- Warehouses
- Stock on hand
- Stock available
- Stock reserved
- Incoming stock
- Batches
- Expiry dates
- Serial numbers
- Unit conversion
- Reorder levels
- Stock adjustments
- Damaged stock
- Transfers
- Receiving
- Dispatch
- Inventory valuation
- Stock history

---

# 19. Customers

The Customer CRM must support:

- Customer profile
- Company
- Contacts
- Address
- Email
- Phone
- Industry
- Products of interest
- Credit terms
- Notes
- Sales quotations
- Orders
- Invoices
- Payments
- Communication history
- Tasks
- Follow-ups
- Customer status

---

# 20. Sales Quotations

The system must support:

- Sales quotation number
- Customer
- Products
- Quantity
- Selling price
- Currency
- Tax
- Shipping
- Validity
- Terms
- Notes
- PDF generation
- Email sending
- Acceptance
- Rejection
- Conversion to order

---

# 21. Orders

Sales orders must support:

- Order number
- Customer
- Products
- Quantity
- Price
- Delivery date
- Warehouse
- Status
- Payment status
- Fulfilment status
- Invoice linkage
- Shipment linkage
- Notes
- Documents

---

# 22. Invoices

Invoices must support:

- Invoice number
- Customer
- Order
- Products
- Quantity
- Unit price
- Tax
- Total
- Currency
- Due date
- Payment terms
- Payment status
- PDF generation
- Email sending
- Partial payments
- Credit notes
- History

---

# 23. Payments

Payments must support:

- Customer payments
- Supplier payments
- Freight payments
- Customs payments
- Warehouse payments
- Currency
- Amount
- Payment method
- Payment date
- Reference
- Invoice link
- Purchase-order link
- Status
- Notes
- Attachments
- Reconciliation

---

# 24. Tasks and Follow-Ups

The task system must support:

- Task
- Owner
- Due date
- Priority
- Status
- Linked supplier
- Linked customer
- Linked RFQ
- Linked quotation
- Linked shipment
- Linked invoice
- Reminder
- Notes
- Completion history

---

# 25. Communication

The platform should eventually integrate:

- Email
- Gmail
- Outlook
- WhatsApp links
- Templates
- Follow-up reminders
- Communication history
- RFQ outreach
- Quotation follow-ups
- Shipment updates
- Customer quotations
- Invoice reminders

External messages must always use Dawlat Global Imports & Trading branding.

---

# 26. Internal Intelligence

Internal intelligence may assist with:

- Supplier discovery
- Supplier verification
- Contact extraction
- RFQ drafting
- Email drafting
- Quotation parsing
- Document extraction
- Supplier comparison
- Risk analysis
- Landed-cost analysis
- Follow-up suggestions
- Shipment exception detection
- Customer communication drafts
- Analytics summaries

AI-generated results must include:

- Source
- Confidence
- Review status
- Human approval before sending or committing important decisions

---

# 27. Live Data and Freshness

Every external record must store:

- Data source
- Date discovered
- Date verified
- Last updated
- Verification method
- Confidence score
- Reviewer
- Status

The platform must clearly distinguish:

- Internal confirmed data
- Supplier-provided data
- Public web data
- AI-extracted data
- Estimated data
- Verified data

Prices and quotations must never be treated as current after their expiry date.

---

# 28. Analytics

The platform must provide dashboards for:

## Procurement
- Active suppliers
- RFQs sent
- Response rate
- Quotations received
- Average response time
- Supplier rankings
- Purchase volume

## Logistics
- Shipments in transit
- Delays
- Freight spend
- Port costs
- Customs costs
- Warehouse costs
- Delivery performance

## Sales
- Customers
- Quotations
- Orders
- Revenue
- Outstanding invoices
- Payments received

## Finance
- Landed cost
- Cost variance
- Currency exposure
- Profit
- Margin
- Cash flow
- Payables
- Receivables

Sensitive profitability data must be restricted to approved roles.

---

# 29. Audit and Compliance

The system must record:

- Who created a record
- Who edited a record
- What changed
- When it changed
- Login history
- Password changes
- User activation
- User deactivation
- Record deletion
- Document uploads
- Status changes
- Financial changes
- Approval changes

Important records should be archived rather than permanently deleted.

---

# 30. Notifications

The platform should notify users about:

- RFQ deadlines
- Quotation expiry
- Supplier follow-up
- Shipment delays
- Certificate expiry
- Invoice due dates
- Overdue payments
- Low stock
- Document expiry
- Tasks due
- Sample delivery
- Customs issues
- Biosecurity inspection

---

# 31. Search

The platform should provide global search across:

- Suppliers
- Partners
- Products
- RFQs
- Quotations
- Orders
- Shipments
- Customers
- Invoices
- Payments
- Documents
- Tasks
- Contacts

Search must support filters and permissions.

---

# 32. Production Architecture

## Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Table
- TanStack Query
- Recharts

## Backend
- FastAPI
- Python
- Pydantic
- SQLAlchemy
- Alembic

## Database
- PostgreSQL

## Storage
- Secure object storage

## Authentication
- Secure server-side sessions or JWT
- Refresh tokens
- Role-based access control
- Optional MFA

## Background Work
- Job queue
- Scheduled tasks
- Email processing
- Document parsing
- Supplier refresh jobs
- Notifications

## Infrastructure
- Docker
- GitHub Actions
- Automated tests
- Logging
- Monitoring
- Error reporting
- Database backups
- Staging environment
- Production environment

---

# 33. Development Environments

The project must support:

- Local
- Test
- Staging
- Production

Production data must never be used directly in development.

---

# 34. Testing

The project must include:

- Unit tests
- Integration tests
- Database tests
- Authentication tests
- Permission tests
- API tests
- UI tests
- End-to-end tests
- Security tests
- Backup recovery tests

---

# 35. Performance and Reliability

The platform should include:

- Pagination
- Caching
- Indexed database fields
- Background processing
- Retry logic
- Timeouts
- Rate limiting
- Duplicate prevention
- Idempotent operations
- File-size limits
- Monitoring
- Graceful error handling

---

# 36. Accessibility and User Experience

The platform must provide:

- Responsive layout
- Keyboard navigation
- Readable contrast
- Clear form validation
- Consistent navigation
- Loading states
- Empty states
- Error states
- Confirmation dialogs
- Search and filters
- Export options
- Professional typography
- Consistent Dawlat branding

---

# 37. Current Prototype

The current Streamlit version is the working prototype.

It currently includes:

- Authentication
- Login
- Logout
- Password change
- User management
- Roles
- Supplier CRM
- Supplier directory
- Supplier search
- Supplier edit
- Supplier delete
- Dashboard
- SQLite
- Git
- GitHub
- Navigation
- Initial supplier quotation page

The prototype must remain preserved as a reference and working internal tool while the enterprise version is developed.

---

# 38. Implementation Order

## Foundation
1. Authentication verification
2. Roles and permissions
3. Audit logging
4. Company settings
5. Database migrations
6. Testing
7. GitHub cleanup
8. README

## Procurement
9. Partner Directory
10. Products
11. Supplier Discovery
12. RFQs
13. Supplier Quotations
14. Supplier Comparison
15. Samples
16. Purchase Orders

## Logistics
17. Freight Forwarders
18. Customs Brokers
19. Ports
20. Warehouses and 3PL
21. Landed Cost
22. Shipments
23. Documents

## Operations
24. Inventory
25. Tasks
26. Notifications

## Sales
27. Customers
28. Sales Quotations
29. Orders
30. Invoices
31. Payments

## Intelligence
32. Document extraction
33. Quotation extraction
34. Supplier scoring
35. Search refresh
36. Internal assistant
37. Recommendations

## Production
38. PostgreSQL
39. FastAPI
40. Next.js
41. Docker
42. Automated tests
43. Staging
44. Production deployment

---

# 39. Definition of Done

A module is only complete when it includes:

- Database design
- Business logic
- Permissions
- Validation
- User interface
- Error handling
- Tests
- Documentation
- Audit logging
- Search
- Export where relevant
- Security review
- Git commit
- Successful end-to-end test

---

# 40. Final Goal

The final platform must allow Dawlat Global Imports & Trading to manage the complete international trade lifecycle from discovering a supplier anywhere in the world to delivering products into an Australian warehouse, selling to customers, collecting payments, and analysing performance.

The platform must become more valuable over time as it builds Dawlat Global's private supplier, quotation, logistics, cost, customer, and performance knowledge base.