# 🧬 Medical Graph RAG — Research Assistant

A production-ready **GraphRAG** application that transforms medical documents into an
interactive knowledge graph, enabling natural-language Q&A with visual subgraph retrieval.

Built with **FastAPI · Neo4j · GPT-4o · React · react-force-graph-2d**.

---

## Architecture

```
User uploads PDF/TXT
      │
      ▼
FastAPI Backend
  ├─ document_processor  →  Extract + chunk text
  ├─ entity_extractor    →  GPT-4o extracts entities & relationships (JSON)
  ├─ graph_manager       →  Store in Neo4j + vector embeddings
  └─ rag_pipeline        →  Embed question → vector search → subgraph → GPT-4o answer
      │
      ▼
Neo4j Knowledge Graph
      │
      ▼
React Frontend
  ├─ FileUpload          →  Drag & drop ingestion
  ├─ ChatInterface       →  Q&A chat with source chips
  └─ GraphVisualization  →  Interactive force-directed subgraph (react-force-graph-2d)
```

### Entity Types Extracted
| Type | Description |
|------|-------------|
| `Disease` | Medical conditions (Diabetes, Hypertension, etc.) |
| `Drug` | Medications and compounds (Metformin, Semaglutide) |
| `Gene` | Genetic markers (TCF7L2, PPARG, KCNJ11) |
| `Symptom` | Clinical signs (Polyuria, Fatigue, Blurred Vision) |
| `TreatmentProtocol` | Clinical guidelines (ADA Diabetes Protocol) |
| `BloodTest` | Lab tests (HbA1c, Fasting Glucose, Lipid Panel) |

### Relationship Types
`TREATS · CAUSES · INHIBITS · ASSOCIATED_WITH · DIAGNOSES · MEASURES · PART_OF · INDICATES · PRESCRIBED_FOR · MONITORS`

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| LLM | OpenAI GPT-4o |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Graph DB | Neo4j 5.19 (vector index native) |
| Frontend | React 18, Vite 5 |
| Graph Viz | react-force-graph-2d |
| DevOps | Docker, Docker Compose |

---

## Prerequisites

- **Docker Desktop** (running) → [Install](https://docs.docker.com/get-docker/)
- **Node.js 18+** → `node --version`
- **Python 3.12** → `python --version`
- **OpenAI API Key** → [Get one](https://platform.openai.com/api-keys)

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/Hasnain-Azam/medical-graph-rag.git
cd medical-graph-rag
```

### 2. Set up your API key

```bash
cp backend/.env.example backend/.env
# Open backend/.env and paste your OpenAI API key
```

### 3. Start Neo4j + Backend (Docker)

```bash
docker compose up --build
```

- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (user: `neo4j` / pass: `medgraph_password`)

### 4. Start the React Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Usage

1. **Upload a document** — drag & drop a medical PDF/TXT, or click **"Load Sample Dataset"**
2. **Watch the graph build** — entities and relationships appear in the force graph
3. **Ask a question** — type in the chat, e.g. *"How does Metformin treat diabetes?"*
4. **Explore the subgraph** — the relevant knowledge graph fragment highlights automatically
5. **Click "← Full Graph"** to return to the complete overview

---

## Running Without Docker (Local Dev)

```bash
# Neo4j — still recommended via Docker
docker run -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/medgraph_password \
  neo4j:5.19.0

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in your OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install && npm run dev
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF/TXT → ingest into graph |
| `/api/query` | POST | Ask a question → answer + subgraph |
| `/api/graph` | GET | Full graph overview + stats |
| `/api/health` | GET | Health check + Neo4j status |
| `/docs` | GET | Interactive Swagger UI |

---

## Project Structure

```
medical-graph-rag/
├── backend/
│   ├── app/
│   │   ├── main.py               ← FastAPI app entrypoint
│   │   ├── config.py             ← Pydantic settings
│   │   ├── models.py             ← Request/response schemas
│   │   ├── routers/
│   │   │   ├── upload.py         ← POST /api/upload
│   │   │   └── query.py          ← POST /api/query, GET /api/graph
│   │   └── services/
│   │       ├── document_processor.py  ← PDF/TXT → chunks
│   │       ├── entity_extractor.py    ← GPT-4o entity extraction
│   │       ├── graph_manager.py       ← Neo4j driver + vector search
│   │       └── rag_pipeline.py        ← Full GraphRAG pipeline
│   ├── data/samples/             ← Demo medical dataset
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx               ← Root layout
│   │   ├── components/
│   │   │   ├── FileUpload.jsx    ← Drag & drop uploader
│   │   │   ├── ChatInterface.jsx ← Chat Q&A
│   │   │   ├── GraphVisualization.jsx ← Force graph
│   │   │   └── StatusBar.jsx     ← Top nav
│   │   └── services/api.js       ← Axios API client
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## License

MIT — feel free to use this as a portfolio project or starting point for medical AI applications.
