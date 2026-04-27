---
name: pdf-helper
description: Use when the user works with .pdf files — extract text, merge, split, rotate, or fill PDF forms.
---

# pdf-helper

## When to Use
- The user references a `.pdf` file.
- The user asks to merge, split, rotate, or OCR a PDF.

## Workflow
1. Parse the user's intent (extract / merge / split / rotate / fill).
2. Call `scripts/run.py <subcommand> <args>`.
3. Return the output path to the user.
