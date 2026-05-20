"""
Local LLM support using Qwen2.5-7B-Instruct from Hugging Face.
"""

from typing import Any

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None

# Global model and tokenizer cache
_model = None
_tokenizer = None
_device = None


def initialize_local_llm(model_name: str = "Qwen/Qwen2.5-7B-Instruct") -> None:
    """
    Initialize the local LLM model and tokenizer.
    Call this once at application startup.
    
    Args:
        model_name: HuggingFace model name (default: Qwen2.5-7B-Instruct)
    """
    global _model, _tokenizer, _device
    
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("transformers package is required for local LLM. Install with: pip install transformers torch")
    
    if _model is not None:
        return  # Already initialized
    
    print(f"Loading local LLM model: {model_name}")
    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",  # Automatically use GPU if available
        torch_dtype="auto",
    )
    _device = _model.device
    print(f"Local LLM model loaded successfully on device: {_device}")


def run_local_prompt(
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    """
    Run a prompt using the local LLM.
    
    Args:
        prompt: The prompt text
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0-2.0)
        top_p: Nucleus sampling parameter
    
    Returns:
        Generated text response
    """
    global _model, _tokenizer, _device
    
    if _model is None:
        raise RuntimeError("Local LLM not initialized. Call initialize_local_llm() first.")
    
    # Prepare messages in chat format
    messages = [
        {"role": "user", "content": prompt},
    ]
    
    # Apply chat template
    text = _tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )
    
    # Tokenize
    model_inputs = _tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=4096,
    ).to(_device)
    
    # Generate
    with torch.no_grad():
        generated_ids = _model.generate(
            **model_inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=_tokenizer.eos_token_id,
        )
    
    # Decode - only new tokens
    response_text = _tokenizer.decode(
        generated_ids[0][model_inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True,
    )
    
    return response_text.strip()


def run_local_prompt_json(
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.3,  # Lower temp for JSON consistency
) -> dict[str, Any]:
    """
    Run a prompt expecting JSON response, using local LLM.
    
    Args:
        prompt: The prompt text
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (lower for JSON)
    
    Returns:
        Parsed JSON dict response
    """
    import json
    
    response_text = run_local_prompt(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    # Try to parse as JSON
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # If not valid JSON, wrap in error response
        return {
            "error": "Invalid JSON response",
            "raw": response_text,
        }
