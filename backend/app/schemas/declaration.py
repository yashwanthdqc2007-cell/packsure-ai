"""
Pydantic schemas for mandatory declaration fields.

Fields required by Legal Metrology (Packaged Commodities) Rules, 2011:
- Manufacturer/packer name and address
- Net quantity (weight/volume/count)
- MRP (Maximum Retail Price)
- Date of manufacture / expiry / best before
- Batch/lot number
- Consumer care contact
- Country of origin (for imported goods)

TODO (Backend Dev):
- Define ExtractedDeclaration schema with all mandatory fields
- Each field should capture: raw_value, normalized_value, confidence, bounding_box
"""

# TODO: Implement declaration schemas
