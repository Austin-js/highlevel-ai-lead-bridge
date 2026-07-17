# HighLevel workflow setup

1. Choose a trigger, such as form submission, contact creation, or appointment booking.
2. Add a webhook action to the workflow.
3. Set the destination to `https://your-domain.example/webhooks/highlevel` and choose `POST`.
4. Add the `X-Webhook-Secret` header, using the same private value as `WEBHOOK_SHARED_SECRET`.
5. Map the event id, event type, contact id, contact fields, source, and custom fields.
6. Send a test event and inspect the API response and logs.
7. Confirm the Slack/Discord handoff if notifications are enabled.
8. Enable optional HighLevel synchronization only after verifying the contact-update permissions of the API token.

The integration accepts the sample shape in `examples/new_lead.json`. It treats email and phone as optional, but a contact id is necessary for optional contact synchronization.

## Optional contact synchronization

When `HIGHLEVEL_SYNC_ENABLED=true`, the service can create a contact note, add tags, and update a configured recommended-action custom field. The implementation uses the documented HighLevel contact note (`POST /contacts/:contactId/notes`), tag (`POST /contacts/:contactId/tags`), and contact update (`PUT /contacts/:contactId`) endpoints. See the [HighLevel contact notes documentation](https://marketplace.gohighlevel.com/docs/ghl/contacts/create-note/), [tag documentation](https://marketplace.gohighlevel.com/docs/ghl/contacts/add-tags/), and [contact update documentation](https://marketplace.gohighlevel.com/docs/ghl/contacts/update-contact/).

Use a least-privilege token, store it in your deployment secret manager, and test against a non-production contact before enabling automation broadly.
