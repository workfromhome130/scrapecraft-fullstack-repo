# ScrapeCraft - AI-Powered Web Scraping Editor

ScrapeCraft is a web-based scraping editor similar to Cursor but specialized for web scraping. It uses AI assistance to help users build scraping pipelines with the ScrapeGraphAI API.

## Features

- 🤖 AI-powered assistant using OpenRouter (Kimi-k2 model)
- 🔗 Multi-URL bulk scraping support
- 📋 Dynamic schema definition with Pydantic
- 💻 Python code generation with async support
- 🚀 Real-time WebSocket streaming
- 📊 Results visualization (table & JSON views)
- 🔄 Auto-updating deployment with Watchtower

## Tech Stack

- **Backend**: FastAPI, LangGraph, ScrapeGraphAI
- **Frontend**: React, TypeScript, Tailwind CSS
- **Database**: PostgreSQL
- **Cache**: Redis
- **Deployment**: Docker, Docker Compose, Watchtower

## Prerequisites

- Docker and Docker Compose
- OpenRouter API key
- ScrapeGraphAI API key

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd scrapecraft
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the application**
   ```bash
   docker compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd frontend
npm install
npm start
```

## Usage

1. **Create a Pipeline**: Click "New Pipeline" to start
2. **Add URLs**: Use the URL Manager to add websites to scrape
3. **Define Schema**: Create fields for data extraction
4. **Generate Code**: Ask the AI to generate scraping code
5. **Execute**: Run the pipeline to scrape data
6. **Export Results**: Download as JSON or CSV

## Remote Updates

The application includes Watchtower for automatic updates:

1. Push new Docker images to your registry
2. Watchtower will automatically detect and update containers
3. No manual intervention required

## API Endpoints

- `POST /api/chat/message` - Send message to AI assistant
- `GET /api/pipelines` - List all pipelines
- `POST /api/pipelines` - Create new pipeline
- `PUT /api/pipelines/{id}` - Update pipeline
- `POST /api/pipelines/{id}/run` - Execute pipeline
- `WS /ws/{pipeline_id}` - WebSocket connection

## Environment Variables

| Variable | Description |
|----------|-------------|
| OPENROUTER_API_KEY | Your OpenRouter API key |
| SCRAPEGRAPH_API_KEY | Your ScrapeGraphAI API key |
| JWT_SECRET | Secret key for JWT tokens |
| DATABASE_URL | PostgreSQL connection string |
| REDIS_URL | Redis connection string |

## License

MIT