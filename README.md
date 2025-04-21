# Neo4j FastAPI Demo Application

This is a simple FastAPI application that demonstrates how to interact with a Neo4j graph database. It provides a RESTful API for creating, reading, updating, and deleting Person nodes, as well as creating and querying relationships between them.

## Running with Docker

The easiest way to get started is using Docker Compose, which will set up both the Neo4j database and the FastAPI application:

```bash
# Build and start the services
docker-compose up -d

# To stop the services
docker-compose down
```

The services will be available at:
- FastAPI application: http://localhost:8000
- Neo4j Browser: http://localhost:7474

## Manual Setup

### Prerequisites

- Python 3.8+
- Docker (for running Neo4j)
- Neo4j instance (can be run in Docker as shown earlier)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure Neo4j Connection

The application uses environment variables to connect to Neo4j. You can:
1. Update the values in the `.env` file
2. Set environment variables manually
3. Use the default values (Neo4j on localhost)

### Run the Application

Start the FastAPI application:

```bash
uvicorn app.main:app --reload
```

The application will be available at http://localhost:8000

## Building the Docker Image

To build the Docker image manually:

```bash
docker build -t neo4j-fastapi-app .
```

Run the container:

```bash
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://your-neo4j-host:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=password123 \
  neo4j-fastapi-app
```

## API Documentation

Once the server is running, you can access the auto-generated API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Web Interface

The application includes two web pages:

1. **People Management Page** (http://localhost:8000/)
   - Add, view, and delete people
   - Create relationships between people
   - View relationships for a specific person

2. **Graph Visualization** (http://localhost:8000/visualize)
   - Interactive visualization of the graph database
   - Shows people as nodes and relationships as edges
   - Allows zooming, dragging, and exploring the graph structure

## API Endpoints

### Person Endpoints

- `GET /people/` - List all people
- `POST /people/` - Create a new person
- `GET /people/{person_id}` - Get a specific person by ID
- `PUT /people/{person_id}` - Update a person
- `DELETE /people/{person_id}` - Delete a person

### Relationship Endpoints

- `POST /relationships/` - Create a relationship between two people
- `GET /people/{person_id}/relationships` - Get all relationships for a person

## Testing the API

You can use the included `test_neo4j_api.py` script to run a series of tests against the API:

```bash
# Make sure the API is running first
python test_neo4j_api.py
```

This will create test users, relationships, query the data, and perform updates and deletions.

## Graph Data Model

This simple example demonstrates a graph with:

- **Nodes**: Person with properties (name, age, email)
- **Relationships**: Custom-named relationships between Person nodes

## Neo4j Browser

You can explore the graph data directly using the Neo4j Browser at http://localhost:7474

Sample Cypher queries:

```cypher
// View all Person nodes
MATCH (p:Person) RETURN p

// View all relationships
MATCH p=()-[r]->() RETURN p

// Find a specific person by property
MATCH (p:Person {name: 'Alice Smith'}) RETURN p

// Find relationships between people
MATCH (p1:Person)-[r]->(p2:Person) 
RETURN p1.name, type(r), p2.name
```

## Monitoring

The application includes monitoring capabilities using Prometheus:

### Monitoring Services

- **Prometheus** (http://localhost:9090)
  - Collects metrics from the FastAPI application, Neo4j, and Postgres
  - Provides a query interface for metrics data
  - Stores time-series data for historical analysis

- **Postgres Exporter** (http://localhost:9187/metrics)
  - Exposes Postgres metrics for Prometheus to scrape
  - Monitors database performance and health

### Accessing Monitoring Tools

After starting the application with `docker-compose up -d`, you can access:

- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)
  - Use the query interface to explore metrics
  - Check targets at [http://localhost:9090/targets](http://localhost:9090/targets) to ensure all services are being scraped
  - View and query metrics using PromQL (Prometheus Query Language)

### Available Metrics

- Postgres database metrics:
  - Database size
  - Connection counts
  - Transaction rates (commits/rollbacks)
  - Query statistics
- Neo4j metrics (via Prometheus scraping)
