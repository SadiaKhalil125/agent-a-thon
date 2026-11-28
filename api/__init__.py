"""HTTP routes. Validate input, enforce the step budget, shape responses.

Routes NEVER call LiteLLM directly (they go through orchestration -> agents).
"""
