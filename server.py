import os
import glob
import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.graph_builder import build_graph, load_extraction
from app.config import EXTRACTIONS_DIR, OUTPUT_DIR
from app.chatbot import answer_question

# Matikan log yang berisik
logging.getLogger("app.graph_builder").setLevel(logging.CRITICAL)
logging.getLogger("app.entity_resolver").setLevel(logging.CRITICAL)
logging.getLogger("app.query_resolver").setLevel(logging.CRITICAL)

app = FastAPI(title="GraphRAG Visualizer Server")

# Initialize graph globally
graph = None

def get_graph():
    global graph
    if graph is None:
        print("[INIT] Memuat cache ekstraksi paper...")
        json_files = glob.glob(os.path.join(EXTRACTIONS_DIR, '*.json'))
        json_files = [f for f in json_files if not f.endswith("entity_aliases.json")]
        extractions = [e for jf in json_files if (e := load_extraction(jf))]
        print("[INIT] Membangun graf pengetahuan...")
        graph = build_graph(extractions)
        print(f"[INIT] Graf siap ({graph.number_of_nodes()} node, {graph.number_of_edges()} edge).")
    return graph

class ChatRequest(BaseModel):
    query: str

@app.on_event("startup")
async def startup_event():
    get_graph() # Preload graph

@app.get("/")
async def get_index():
    # Mengembalikan file graph.html utama
    html_path = os.path.join(OUTPUT_DIR, "graph.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Error: graph.html tidak ditemukan. Jalankan 'python main.py' terlebih dahulu.</h1>", status_code=404)

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    g = get_graph()
    answer = answer_question(req.query, g)
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time
    
    print("="*60)
    print(" Menjalankan GraphRAG Visualizer Server")
    print("="*60)
    
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8000")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
