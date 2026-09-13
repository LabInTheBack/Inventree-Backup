# InvenTree Conversation Handoff

Updated 2026-09-13. This is a short continuation note, not a replacement for the live database.

## Start Here

- Workspace: `/home/den/server-data/inventree`.
- Read the core rules in `docs/part-creation-rules.md`, then the relevant family section only.
- All approved database cleanup and keyword tasks are complete. No pending approved TODOs.
- Do not repeat the full audit on startup. Await the next specific task and query only relevant data.
- Never rename drawers or change WLED/plugin logic. Printed labels are not warehouse location names.
- Reuse templates, companies, parts and images. Add supplied quantities to existing stock rather than replacing totals.
- No supplier availability tracking. Price breaks come from the user in EUR.
- Supplier media: local exact image first; at most two quick image attempts and two quick datasheet attempts on DigiKey.com. Do not scan PDFs or search elsewhere for missing assets.

## Database Access

Use the running container; do not restart it for routine entry:

```bash
docker compose exec -T -w /home/inventree/src/backend/InvenTree inventree-server python3 manage.py shell
```

Relevant models: `part.models.Part`, `PartCategory`, `PartCategoryParameterTemplate`; `common.models.Parameter`, `ParameterTemplate`; `company.models.Company`, `ManufacturerPart`, `SupplierPart`, `SupplierPriceBreak`; `stock.models.StockItem`, `StockLocation`.

Parameters use a generic relation: filter `model_type__model="part", model_id=part.pk`. Inspect current fields and units before writes. Use transactions for multi-record changes, verify only intended fields changed, and never print secrets. For audits, use a read-only database transaction. Resolve live IDs instead of relying on historical IDs.

## Completed Cleanup

- Raspberry Pi Zero 1 W corrected to SC0020, distinct from Zero 2 WH.
- Manufacturer names consolidated; canonical examples: Onsemi, Diodes Inc, Murata Electronics, Vishay.
- Linked 21 stock records to supplier parts and 51 supplier parts to manufacturer parts where identity was unambiguous.
- Removed unused `Hight` and `Package (in)`. Kept logical unused templates and distinct Voltage/Voltage Rating fields.
- Corrected 22 typical/unqualified parameter assignments across 13 parts. Added neutral offset, bias, supply-current and quiescent-current templates rather than falsely labeling maxima.
- Repaired numeric indexes for existing unit aliases and one stale microphone current index. Preserve unit semantics, including RMS and A-weighting.
- Standardized uA, `Module / Board`, and the `Sensor Module` choice.
- Moved Distance Proximity under Position, Proximity & Touch. XL6009 switching-frequency value uses neutral Frequency, with its switching context in the note.
- Added 541 category-template links across 65 categories; removed only the generic Power links on Capacitors and Inductors. Total 564 links at completion; all default values blank. No backfill of part parameters.
- Reviewed 178 parts; appended the approved factual search keywords to 31 parts. Existing keywords were preserved.
- Part values, stock, prices, drawer names and WLED mappings were preserved during the category-default and keyword tasks.

## Observations Only: No Cleanup Authorized

- Prusa Brass CHT nozzle keywords include `obxidian`.
- Several memory cards have mixed SDHC/SDXC terms; full-size Transcend SDHC also has `microsd`.
- Generic breadboard PSU keywords contain both Microchip and SparkFun identifiers despite uncertain identity.

Do not remove these keywords without explicit approval. These are not pending approved tasks.

## Documentation Boundaries

The two maintenance guides contain historical `/home/denys/inventree` examples. Do not execute those paths as-is here; inspect the actual deployment before infrastructure work. `docs/wled-locator-plus.md` is plugin documentation, not a reason to inspect or modify the plugin during catalog entry.
