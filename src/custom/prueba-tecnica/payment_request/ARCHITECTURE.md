# Payment Request — Architecture decisions

Each request and approval level belongs to one company. Record rules restrict
requests to the requester's own requests, requests assigned to the current
approver, or requests in a treasury user's allowed companies. Approval levels
are also limited to allowed companies.

State transitions lock the affected request rows with PostgreSQL
`SELECT ... FOR UPDATE`, ordered by record ID. The lock is held until the
transaction ends. A concurrent transition waits, reloads the state and is
rejected if the first transaction already changed it.

The request keeps its original currency and amount. When Treasury pays, the
wizard converts that amount to the selected bank/cash journal currency using
Odoo's currency rates for the payment date and request company. Creating,
posting and linking the payment happen in one transaction; a failure rolls
back the payment and leaves the request approved.
