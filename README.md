# AI Teacher Nexus

## Setup

1. **Create Virtual Environment**
   ```bash
   python -m venv tcagents
   ```

2. **Activate Virtual Environment**
   - Windows: `tcagents\Scripts\activate`
   - Linux/macOS: `source tcagents/bin/activate`

3. **Install Dependencies**
   ```bash
   pip install -e .
   ```

## Running the Demo

```bash
python src/main.py
```

## Directory Structure

- `src/core`: Core infrastructure (Factory, Lifecycle, State)
- `src/supervisor`: Supervisor agent (Router)
- `src/teachers`: Specialized teachers (Marketing, Training)
- `src/shared`: Shared tools and RAG
- `config`: Configuration and Prompts
- `logs`: Audit logs
