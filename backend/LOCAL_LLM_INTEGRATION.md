# Local LLM Integration Guide

## Overview
This project now supports both HTTP-based LLM API and local HuggingFace models. Currently integrated with **Qwen2.5-7B-Instruct**.

## Architecture

### Components

1. **llm_local.py** - Local LLM module
   - `initialize_local_llm()` - Loads model and tokenizer at startup
   - `run_local_prompt()` - Generates text response
   - `run_local_prompt_json()` - Generates JSON response (for structured data)

2. **llm_client.py** - Updated LLM client (unified interface)
   - Supports both HTTP API and local models
   - Constructor parameters:
     - `use_local` (bool) - Switch between local/HTTP
     - `local_model_name` (str) - HuggingFace model identifier
     - `api_llm` (str) - HTTP API URL (for fallback)
     - `timeout_seconds` (float) - Request timeout

3. **config.py** - Configuration settings
   - `USE_LOCAL_LLM` - Environment variable to enable local LLM
   - `LOCAL_LLM_MODEL` - Model identifier
   - Backward compatible with existing `API_LLM` setting

## Installation

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

Key packages:
- `transformers>=4.41.0` - HuggingFace model library
- `torch>=2.1.0` - PyTorch (CPU or GPU variant)

For GPU support, install GPU-compatible PyTorch:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118  # CUDA 11.8
# or
pip install torch --index-url https://download.pytorch.org/whl/cu121  # CUDA 12.1
```

### 2. Configure Environment

Create `.env` file or update existing:
```bash
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
API_LLM=http://localhost:8080/dump  # Ignored when USE_LOCAL_LLM=true
DATABASE_URL=postgresql+asyncpg://progressors:progressors@postgres:5432/progressors
TELEGRAM_BOT_TOKEN=your_token_here
```

## Usage

### Switching Modes

**HTTP API Mode (default):**
```bash
USE_LOCAL_LLM=false
API_LLM=http://your-llm-api.com/endpoint
```

**Local LLM Mode:**
```bash
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

### First Run

First execution will download the model (~15GB for Qwen2.5-7B-Instruct):
```
Loading local LLM model: Qwen/Qwen2.5-7B-Instruct
[Downloads model files to ~/.cache/huggingface/hub/]
Local LLM model loaded successfully on device: cuda:0
```

Model is cached after first download for faster subsequent runs.

## Model Details

### Qwen2.5-7B-Instruct
- **Size**: ~15GB VRAM
- **Input**: Text prompts (can handle multiple tokens)
- **Output**: Generated text (configurable max_tokens)
- **Hardware**: Works on GPU (NVIDIA with CUDA) or CPU (slower)

### Key Features
- Chat template support (role-based messages)
- Configurable generation parameters:
  - `max_tokens` - Maximum output length (default: 2048)
  - `temperature` - Randomness of output (0.0-2.0, lower = more deterministic)
  - `top_p` - Nucleus sampling (0.0-1.0)

## API Endpoints (Unchanged)

All endpoints continue to work with both modes:

- `POST /api/profile/analyze` - Profile analysis
- `POST /api/roadmap/generate` - Roadmap generation  
- `POST /api/roadmap/{id}/feedback` - Roadmap feedback/correction
- `GET /api/profile/{telegram_id}` - Get user profile
- `GET /api/roadmap/{roadmap_id}` - Get roadmap
- `GET /api/roadmap/{roadmap_id}/items` - List roadmap items
- `GET /api/roadmap/{roadmap_id}/item/{item_id}/test` - Get mini-test
- `POST /api/roadmap/item/complete` - Complete roadmap item (calculates XP)

## Performance Considerations

### Local Model
- **First request**: ~5-30 seconds (model initialization)
- **Subsequent requests**: ~2-10 seconds (depends on prompt length, output length, hardware)
- **Memory**: ~15GB VRAM for Qwen2.5-7B
- **No network latency**: Faster for local inference

### HTTP API
- **Per request**: ~1-5 seconds (depends on API server)
- **Network latency**: Varies based on connection quality
- **Memory**: Minimal (only need to store request/response)

## Troubleshooting

### Model Download Issues
```
FileNotFoundError: Model not found
→ Check internet connection
→ Ensure write permissions to ~/.cache/huggingface/
→ Try manual download: huggingface-cli login && huggingface-cli download Qwen/Qwen2.5-7B-Instruct
```

### Out of Memory (OOM)
```
CUDA out of memory
→ Use CPU mode: Add code to force CPU usage
→ Use smaller model: e.g., Qwen2.5-1.5B-Instruct
→ Reduce max_tokens parameter
```

### Slow Response Times
```
Check GPU utilization: nvidia-smi
If CPU-bound: Consider GPU acceleration
If memory-bound: Reduce batch size or use smaller model
```

## Code Examples

### Using Local LLM Directly
```python
from app.llm_local import initialize_local_llm, run_local_prompt_json

# At app startup
initialize_local_llm("Qwen/Qwen2.5-7B-Instruct")

# Later in request handler
response = run_local_prompt_json(
    prompt="Generate a learning roadmap for...",
    max_tokens=2048,
    temperature=0.3  # Lower for structured output
)
```

### Using LlmClient (Recommended)
```python
from app.llm_client import LlmClient
from app.config import get_settings

settings = get_settings()

llm = LlmClient(
    api_llm=settings.api_llm,
    timeout_seconds=settings.llm_timeout_seconds,
    use_local=settings.use_local_llm,
    local_model_name=settings.local_llm_model,
)

output = await llm.run_prompt(
    prompt_name="profile_analysis",
    prompt=prompt_text,
    variables={"key": "value"},
)
```

## Future Enhancements

Possible improvements:
- [ ] Model quantization (4-bit, 8-bit) to reduce memory
- [ ] Multiple model support with automatic switching
- [ ] Prompt caching for repeated requests
- [ ] Batch processing for multiple requests
- [ ] Integration with vLLM or TensorRT for optimization
- [ ] Support for smaller/faster models (Qwen2.5-1.5B, Phi-3)

## References

- [Qwen2.5 on HuggingFace](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
- [Transformers Library Documentation](https://huggingface.co/docs/transformers)
- [PyTorch Installation Guide](https://pytorch.org/get-started/locally/)
