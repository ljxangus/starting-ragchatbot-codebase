# AGENTS.md

This file contains guidelines for agentic coding assistants working in this repository.

## Build and Run Commands

### Backend (FastAPI)
- **Install dependencies**: `uv sync`
- **Run development server**: `cd backend && uv run uvicorn app:app --reload --port 8000`
- **Quick start**: `./run.sh` (from root directory)
- **Test API key**: `python test_api_key.py`

### Frontend
- Frontend is served statically by FastAPI at `http://localhost:8000`
- No separate build process required (vanilla JS)

### Testing
- No formal test framework configured
- Use `python test_api_key.py` to verify Zhipu AI API key
- Manual testing via `http://localhost:8000/docs` (FastAPI auto-generated docs)

## Code Style Guidelines

### Python Backend

#### Imports
- Order: standard library → third-party → local imports
- Group imports with blank lines between sections
- Use `from typing import List, Optional, Dict, Any` for type hints

#### Naming Conventions
- Classes: PascalCase (RAGSystem, VectorStore, DocumentProcessor)
- Functions/Methods: snake_case
- Variables: snake_case
- Constants: UPPER_SNAKE_CASE (SYSTEM_PROMPT, CHUNK_SIZE)
- Private methods: _prefix (_resolve_course_name, _build_filter)

#### Type Hints
- Always use type hints for function signatures
- Use `Optional[str]` for nullable types
- Use `List[str]`, `Dict[str, Any]` for collections
- Use `Tuple[Type1, Type2]` for multiple return values

#### Classes and Dataclasses
- Use `@dataclass` for simple configuration classes (config.py)
- Use Pydantic `BaseModel` for request/response models
- Include docstrings for all classes and public methods

#### Error Handling
- Use try/except blocks with descriptive error messages
- Print errors to console for debugging
- Raise `HTTPException` for API endpoints with status codes
- Return empty results or None for non-critical failures

#### String Formatting
- Use f-strings for string interpolation
- Use triple quotes for multi-line strings (system prompts)

### Frontend (JavaScript)

#### Code Style
- Use `const` and `let` (no `var`)
- Use async/await for API calls
- Use arrow functions for callbacks
- Use template literals for string interpolation

#### DOM Manipulation
- Cache DOM elements in global variables at initialization
- Use `document.getElementById` and `querySelector`
- Use `addEventListener` for event handling

#### API Calls
- Use relative paths (`/api/query`, `/api/courses`)
- Handle errors with try/catch blocks
- Parse JSON responses with `response.json()`

## Project Structure

```
backend/
├── app.py              # FastAPI application and endpoints
├── config.py           # Configuration (dataclass)
├── models.py           # Pydantic models (Course, Lesson, CourseChunk)
├── rag_system.py       # Main RAG orchestrator
├── vector_store.py     # ChromaDB vector storage
├── document_processor.py  # Text chunking and parsing
├── ai_generator.py     # Zhipu AI integration
├── session_manager.py  # Conversation history
└── search_tools.py     # Tool-based search for AI

frontend/
├── index.html          # Main HTML
├── script.js           # Client-side JavaScript
└── style.css           # Styling

docs/                  # Course materials (txt files)
```

## Key Dependencies

- **FastAPI**: Web framework
- **ChromaDB**: Vector database
- **Zhipu AI**: GLM-4 model for generation
- **Sentence Transformers**: Embeddings (all-MiniLM-L6-v2)
- **Pydantic**: Data validation

## Configuration

- Environment variables loaded from `.env` file
- Required: `ZHIPU_API_KEY`
- Configured in `backend/config.py` as dataclass
- Default model: `glm-4-plus`

## Adding New Features

1. **New API endpoint**: Add to `backend/app.py` with Pydantic models
2. **New model**: Add to `backend/models.py` using Pydantic BaseModel
3. **New RAG component**: Create in `backend/`, import in `rag_system.py`
4. **Frontend feature**: Add to `frontend/script.js`, update HTML/CSS as needed

## Important Notes

- Course documents follow specific format (see `docs/` for examples)
- Vector store persists in `backend/chroma_db/`
- Session history limited to 2 exchanges by default
- Chunk size: 800 chars, overlap: 100 chars
- Max search results: 5