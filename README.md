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

### Basic Interaction
```bash
python src/main.py
```

### Testing Researcher Agent
To verify the new "Researcher" capability (currently using Mock data):
```bash
python src/main.py "Find the latest news about AI Agents in 2024."
```
**Expected Output:**
1. Supervisor routes to `researcher_teacher`.
2. Researcher generates a plan (Mock queries).
3. Researcher executes search (Mock results).
4. Researcher provides a summary.

## Directory Structure

- `src/agents`: All agent logic (Supervisor, Teachers, Researcher)
- `src/services`: Shared services (RAG, etc.)
- `src/core`: Core infrastructure (Config, Logger, State)
- `config`: Configuration and Prompts
- `logs`: Audit logs
