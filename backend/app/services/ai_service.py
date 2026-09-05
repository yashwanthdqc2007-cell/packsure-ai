"""
AI extraction service using Google Gemini.

IMPORTANT ARCHITECTURAL PRINCIPLE:
Gemini is used ONLY to extract and structure information from the image.
Gemini does NOT make compliance decisions.
All compliance decisions are made by the deterministic compliance_service.

TODO (Backend Dev — Phase 2):
- extract_declarations(image, ocr_text) -> ExtractedDeclaration
  - Send image + OCR text to Gemini Vision
  - Use structured output / JSON mode to get field-by-field extraction
  - Map extracted fields to declaration schema
- Prompt must instruct Gemini to extract only, not evaluate compliance
"""

# TODO: Implement Gemini extraction service
