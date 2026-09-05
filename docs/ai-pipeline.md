# PackSure AI — AI Pipeline

Describes how Gemini Vision is used in the extraction pipeline.

## Role of AI

Gemini Vision is used ONLY for extraction and structuring of information from package images. It does NOT make compliance decisions.

## Pipeline

1. Preprocessed image + Tesseract raw OCR text are sent to Gemini
2. Gemini returns structured JSON with extracted declaration fields
3. Each field includes: raw_value, normalized_value, confidence
4. Extracted declarations are passed to the deterministic compliance engine

## Prompt Strategy

TODO:
- Design prompts that instruct Gemini to extract only
- Use JSON structured output mode
- Handle ambiguous or partially visible text
- Handle multilingual packages (Hindi + English)

## Fallback

If Gemini extraction confidence is low, the scan is flagged as NEEDS_REVIEW.
